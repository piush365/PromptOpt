"""Stage C LoRA training, evaluation and prediction. Standalone (no `app` imports), so the same file runs locally and
in Colab (notebooks/train_stage_c.ipynb ships it inside stage_c_data_v1.zip).

    python train.py --data DIR --out DIR                 # verify sha256, train, save the best adapter
    python train.py --data DIR --zero-shot 60            # base model only, no training
    python train.py --data DIR --estimate                # time 20 steps and print the full-run estimate

DIR holds train.jsonl, val.jsonl, config.json and manifest.json (written by app.stage_c.data). Settings come from
config.json. Loss is computed on the assistant tokens only; evaluation decodes greedily.
"""
import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import torch

FIELDS_ALL = ("task", "output_format", "constraints", "category")


# ---------------------------------------------------------------- data
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(data_dir: Path) -> dict:
    """Check the sha256 of every file listed in manifest.json. Raises on any mismatch."""
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, meta in manifest["files"].items():
        got = sha256(data_dir / name)
        if got != meta["sha256"]:
            raise SystemExit(f"sha256 mismatch for {name}: manifest {meta['sha256']}, file {got}")
    print(f"manifest OK: {len(manifest['files'])} files match their sha256 ({manifest['version']})")
    return manifest


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def encode(tok, messages: list[dict], max_length: int) -> dict | None:
    """input_ids + labels (-100 on the system/user part). None if the example does not fit."""
    prompt = tok.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=False)
    full = tok.apply_chat_template(messages, tokenize=False)
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(ids) > max_length or ids[:len(p_ids)] != p_ids:
        return None
    return {"input_ids": ids, "labels": [-100] * len(p_ids) + ids[len(p_ids):]}


def batches(items: list[dict], size: int, pad_id: int, shuffle: bool, rng: random.Random):
    order = list(range(len(items)))
    if shuffle:
        rng.shuffle(order)
    for i in range(0, len(order), size):
        chunk = [items[j] for j in order[i:i + size]]
        n = max(len(x["input_ids"]) for x in chunk)
        ids = torch.full((len(chunk), n), pad_id)
        labels = torch.full((len(chunk), n), -100)
        mask = torch.zeros((len(chunk), n), dtype=torch.long)
        for k, x in enumerate(chunk):
            m = len(x["input_ids"])
            ids[k, :m], labels[k, :m], mask[k, :m] = torch.tensor(x["input_ids"]), torch.tensor(x["labels"]), 1
        yield {"input_ids": ids, "labels": labels, "attention_mask": mask}


# ---------------------------------------------------------------- model
def seed_all(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass


def precision() -> torch.dtype:
    """bf16 where the GPU supports it (Ampere+: RTX 3050), fp16 otherwise (T4), fp32 on CPU."""
    if not torch.cuda.is_available():
        return torch.float32
    return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16


def load_base(cfg: dict, dtype: torch.dtype):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    tok.padding_side = "left"                      # for batched generation; training pads by hand
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(cfg["base_model"], dtype=dtype)
    return tok, model.to("cuda" if torch.cuda.is_available() else "cpu")


def add_lora(model, cfg: dict):
    from peft import LoraConfig, get_peft_model
    lora = cfg["lora"]
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(task_type="CAUSAL_LM", r=lora["r"], lora_alpha=lora["alpha"],
                                             lora_dropout=lora["dropout"], target_modules=lora["target_modules"]))
    for p in model.parameters():                   # adapters in fp32 so fp16/bf16 training stays stable
        if p.requires_grad:
            p.data = p.data.float()
    model.print_trainable_parameters()
    return model


@torch.no_grad()
def val_loss(model, items: list[dict], cfg: dict, pad_id: int, dtype: torch.dtype) -> float:
    model.eval()
    total, count = 0.0, 0
    for b in batches(items, cfg["train"]["eval_batch_size"], pad_id, False, random.Random(0)):
        b = {k: v.to(model.device) for k, v in b.items()}
        with torch.autocast(model.device.type, dtype=dtype, enabled=dtype != torch.float32):
            logits = model(input_ids=b["input_ids"], attention_mask=b["attention_mask"]).logits.float()
        shift_logits, shift_labels = logits[:, :-1], b["labels"][:, 1:]
        loss = torch.nn.functional.cross_entropy(shift_logits.reshape(-1, shift_logits.size(-1)),
                                                 shift_labels.reshape(-1), ignore_index=-100, reduction="sum")
        total += loss.item()
        count += (shift_labels != -100).sum().item()
    model.train()
    return total / max(1, count)


def train(cfg: dict, data_dir: Path, out_dir: Path, max_steps: int | None = None, estimate_only: bool = False) -> dict:
    t = cfg["train"]
    seed_all(cfg["seed"])
    dtype = precision()
    tok, model = load_base(cfg, dtype)
    model = add_lora(model, cfg)
    enc = lambda rows: [x for x in (encode(tok, r["messages"], cfg["max_length"]) for r in rows) if x]
    train_rows = [r for r in load_jsonl(data_dir / "train.jsonl") if r["clean"]]
    train_items, val_items = enc(train_rows), enc(load_jsonl(data_dir / "val.jsonl"))
    print(f"train {len(train_items)} examples (dropped {len(train_rows) - len(train_items)} too long), "
          f"val {len(val_items)}; precision {dtype}; device {model.device}")

    steps_per_epoch = math.ceil(len(train_items) / (t["batch_size"] * t["grad_accum"]))
    total = max_steps or steps_per_epoch * t["epochs"]
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=t["lr"],
                            weight_decay=t["weight_decay"])
    warmup = max(1, int(t["warmup_ratio"] * total))
    sched = torch.optim.lr_scheduler.LambdaLR(        # linear warmup, then linear decay to 0
        opt, lambda s: (s + 1) / warmup if s < warmup else max(0.0, (total - s) / max(1, total - warmup)))
    scaler = torch.amp.GradScaler(enabled=dtype == torch.float16)
    pad_id, rng = tok.pad_token_id, random.Random(cfg["seed"])

    history, best, bad_evals, step, start = [], float("inf"), 0, 0, time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    model.train()
    done = False
    for epoch in range(t["epochs"]):
        micro = 0
        for b in batches(train_items, t["batch_size"], pad_id, True, rng):
            b = {k: v.to(model.device) for k, v in b.items()}
            with torch.autocast(model.device.type, dtype=dtype, enabled=dtype != torch.float32):
                loss = model(**b).loss / t["grad_accum"]
            scaler.scale(loss).backward()
            micro += 1
            if micro % t["grad_accum"]:
                continue
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], t["max_grad_norm"])
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            sched.step()
            step += 1
            if step == 20:
                per = (time.time() - start) / step
                print(f"estimate: {per:.2f} s/step x {total} steps = {per * total / 60:.0f} min "
                      f"(+ evals); peak GPU memory {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB"
                      if torch.cuda.is_available() else f"estimate: {per:.2f} s/step x {total} steps")
                if estimate_only:
                    return {"seconds_per_step": per, "steps": total}
            if step % t["eval_every"] == 0 or step == total:
                vl = val_loss(model, val_items, cfg, pad_id, dtype)
                history.append({"step": step, "epoch": epoch, "train_loss": loss.item() * t["grad_accum"],
                                "val_loss": vl, "minutes": (time.time() - start) / 60})
                print(json.dumps(history[-1]))
                if vl < best - 1e-4:
                    best, bad_evals = vl, 0
                    model.save_pretrained(out_dir / "adapter")
                    tok.save_pretrained(out_dir / "adapter")
                else:
                    bad_evals += 1
                    if bad_evals >= t["patience"]:
                        print(f"early stop at step {step}: val loss did not improve for {bad_evals} evals")
                        done = True
            if step >= total or done:
                done = True
                break
        if done:
            break
    summary = {"best_val_loss": best, "steps": step, "minutes": (time.time() - start) / 60, "history": history,
               "precision": str(dtype), "config": cfg}
    (out_dir / "adapter" / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# ---------------------------------------------------------------- prediction and quick metrics
@torch.no_grad()
def predict(model, tok, rows: list[dict], max_new_tokens: int = 192, batch_size: int = 8) -> list[str]:
    """Greedy decoding of the assistant turn for each example."""
    model.eval()
    model.config.use_cache = True
    outs = []
    for i in range(0, len(rows), batch_size):
        prompts = [tok.apply_chat_template(r["messages"][:-1], add_generation_prompt=True, tokenize=False)
                   for r in rows[i:i + batch_size]]
        enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tok.pad_token_id)
        outs += tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return outs


def parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def quick_metrics(rows: list[dict], outputs: list[str]) -> dict:
    """JSON validity, exact key set, category accuracy, format null/non-null agreement. Full metrics: Phase 3."""
    n = len(rows)
    parsed = [parse_json(o) for o in outputs]
    valid = sum(p is not None for p in parsed)
    keys = sum(p is not None and set(p) == set(r["target"]) for r, p in zip(rows, parsed))
    cat = [(r, p) for r, p in zip(rows, parsed) if "category" in r["target"]]
    fmt = [(r, p) for r, p in zip(rows, parsed) if "output_format" in r["target"]]
    return {"n": n, "json_valid": valid / n, "exact_keys": keys / n,
            "category_acc": (sum(p is not None and p.get("category") == r["target"]["category"] for r, p in cat)
                             / len(cat)) if cat else None,
            "format_presence_agree": (sum(p is not None and bool(p.get("output_format")) ==
                                          bool(r["target"]["output_format"]) for r, p in fmt) / len(fmt))
            if fmt else None}


def eval_rows(data_dir: Path, n: int, seed: int) -> list[dict]:
    """A fixed val sample: all routed examples, then forced ones, so base and LoRA see the same rows."""
    val = load_jsonl(data_dir / "val.jsonl")
    routed = [r for r in val if r["kind"] == "routed"]
    rest = [r for r in val if r["kind"] != "routed"]
    random.Random(seed).shuffle(rest)
    return (routed + rest)[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("stage_c_out"))
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("--estimate", action="store_true", help="time 20 optimizer steps and stop")
    ap.add_argument("--zero-shot", type=int, metavar="N", help="evaluate the base model on N val examples")
    args = ap.parse_args()
    verify(args.data)
    cfg = json.loads((args.data / "config.json").read_text(encoding="utf-8"))
    if args.zero_shot:
        tok, model = load_base(cfg, precision())
        rows = eval_rows(args.data, args.zero_shot, cfg["seed"])
        print(json.dumps(quick_metrics(rows, predict(model, tok, rows)), indent=2))
        return
    summary = train(cfg, args.data, args.out, args.max_steps, args.estimate)
    print(json.dumps({k: v for k, v in summary.items() if k != "history"}, indent=2, default=str))


if __name__ == "__main__":
    main()
