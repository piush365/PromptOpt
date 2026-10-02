"""Load the Stage C model (Qwen2.5-0.5B-Instruct + the LoRA adapter) and generate greedily, one prompt at a time.

    model = StageCModel.load()                      # STAGE_C_ADAPTER, STAGE_C_DEVICE (auto: cuda if available)
    result = apply_stage_c(prompt, features, stage_b_output, model.generate)

`adapter=None` loads the base model only (the zero-shot baseline). torch/transformers/peft are imported lazily, so the
rest of the app runs without them; `available()` says whether Stage C can be used.
"""
from functools import lru_cache
from pathlib import Path

from app.config import STAGE_C_ADAPTER, STAGE_C_BASE_MODEL, STAGE_C_DEVICE

MAX_NEW_TOKENS = 192


def available(adapter: Path = STAGE_C_ADAPTER) -> bool:
    try:
        import peft  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return (Path(adapter) / "adapter_config.json").exists()


class StageCModel:
    def __init__(self, model, tok, device: str, name: str):
        self.model, self.tok, self.device, self.name = model, tok, device, name

    @classmethod
    def load(cls, adapter: Path | None = STAGE_C_ADAPTER, device: str = STAGE_C_DEVICE,
             base_model: str = STAGE_C_BASE_MODEL) -> "StageCModel":
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if device == "cuda" \
            else torch.float32
        tok = AutoTokenizer.from_pretrained(base_model)
        model = AutoModelForCausalLM.from_pretrained(base_model, dtype=dtype)
        name = base_model
        if adapter is not None:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, str(adapter)).merge_and_unload()   # merged: faster inference
            name = f"{base_model} + {Path(adapter).name}"
        model.to(device).eval()
        model.generation_config.pad_token_id = tok.pad_token_id or tok.eos_token_id
        return cls(model, tok, device, name)

    def generate(self, messages: list[dict]) -> str:
        import torch
        text = self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        enc = self.tok(text, return_tensors="pt", add_special_tokens=False).to(self.device)
        with torch.no_grad():
            out = self.model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False, temperature=None,
                                      top_p=None, top_k=None)
        if self.device == "cuda":
            torch.cuda.synchronize()
        return self.tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)


@lru_cache(maxsize=1)
def default_model() -> StageCModel | None:
    """The app's Stage C model, or None when the adapter or the ML packages are missing (Stage B result is used)."""
    return StageCModel.load() if available() else None
