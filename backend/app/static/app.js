// PromptOpt UI: plain JS, no build step. All text from the server is inserted with textContent (never innerHTML).
const $ = (id) => document.getElementById(id);
const LABELS = {
  auto: "Auto-detect", closed_qa: "Question about a text", information_extraction: "Extract information",
  classification: "Classify", summarization: "Summarize", coding: "Coding",
  none: "None", image: "Image", pdf: "PDF", pptx: "Slides (PPTX)", docx: "Word (DOCX)",
  spreadsheet: "Spreadsheet", code: "Code file", other: "Other file",
  claude: "Claude", gpt: "GPT", gemini: "Gemini",
  image_generation: "Image generation", dalle: "DALL-E", nano_banana: "Nano Banana (Gemini image)",
  stable_diffusion: "Stable Diffusion",
  subject_detail: "Subject detail", style: "Style / medium", composition: "Composition / framing",
  lighting: "Lighting", palette: "Color palette", mood: "Mood", aspect_ratio: "Aspect ratio",
  background: "Background", avoid: "Things to avoid",
};
let OPTIONS = null;
let accepted = new Set();                        // image mode: suggestions the user clicked
let shownImage = "dalle";
const isImageMode = () => $("category").value === "image_generation";

function setTargets() {
  const image = isImageMode();
  const targets = image ? OPTIONS.image_targets : ["gpt", "gemini", "claude"];
  $("target_legend").textContent = image ? "Target image model" : "Target LLM";
  $("target_options").replaceChildren(...targets.map((t, i) => {
    const label = el("label"), input = el("input");
    input.type = "radio"; input.name = "target"; input.value = t; input.checked = i === 0;
    label.append(input, " " + (LABELS[t] || t));
    return label;
  }));
  $("attachment_box").hidden = image;
  $("context_box").hidden = image;
}
let last = null;
let shown = "gpt";

function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function fill(select, values) {
  select.replaceChildren(...values.map((v) => { const o = el("option", LABELS[v] || v); o.value = v; return o; }));
}

async function init() {
  const opt = await (await fetch("/api/options")).json();
  OPTIONS = opt;
  fill($("category"), opt.categories);
  fill($("pick"), opt.categories.filter((c) => c !== "auto" && c !== "image_generation"));
  setTargets();
  $("category").addEventListener("change", setTargets);
  fill($("attachment"), opt.attachment_types);
  $("retention").textContent = `(kept ${opt.retention_days} days)`;
  $("attachment").addEventListener("change", () => { $("attachment_name").hidden = $("attachment").value === "none"; });
  loadHistory();
}

function showTarget(t) {
  shown = t;
  for (const b of $("tabs").children) b.setAttribute("aria-selected", b.dataset.target === t);
  $("rendered").textContent = last.renderings[t];
  const tk = last.tokens[t];
  $("tokens").textContent = `${tk.tokens} input tokens for ${LABELS[t]} (${tk.exact ? "exact, " : ""}${tk.method})`;
}

function showImage(t) {
  shownImage = t;
  const r = last.renderings[t];
  for (const b of $("image_tabs").children) b.setAttribute("aria-selected", b.dataset.target === t);
  $("image_prompt").textContent = r.prompt;
  $("negative_box").hidden = !r.negative_prompt;
  $("negative_prompt").textContent = r.negative_prompt || "";
  const params = Object.entries(r.params).map(([k, v]) => `${k} ${v}`).join(", ");
  $("image_params").textContent = (params ? "Parameters: " + params : "No parameters") +
    (last.aspect_ratio ? "" : " (no aspect ratio stated: the model's default size)");
}

function renderImage(r) {
  last = r;
  $("result").hidden = true;
  $("coding_panel").hidden = true;
  $("image_result").hidden = false;
  $("image_tabs").replaceChildren(...OPTIONS.image_targets.map((t) => {
    const b = el("button", LABELS[t] + (t === r.target ? " (selected)" : ""));
    b.type = "button"; b.dataset.target = t; b.setAttribute("role", "tab");
    b.addEventListener("click", () => showImage(t));
    return b;
  }));
  showImage(r.target);
  const stated = Object.entries(r.stated);
  $("image_stated").replaceChildren(...(stated.length ? stated.map(([a, ev]) => el("li", `${LABELS[a] || a}: ${ev.join(", ")}`))
                                                     : [el("li", "Only the subject.", "muted")]));
  $("image_avoid").replaceChildren(...(r.avoid_user.length ? r.avoid_user.map((x) => el("li", x))
                                                         : [el("li", "Nothing.", "muted")]));
  $("image_auto").replaceChildren(...(r.auto_added.length ? r.auto_added.map((a) => {
    const li = el("li"); li.append(el("strong", a.what + ":"), " " + a.value); return li;
  }) : [el("li", "Nothing.", "muted")]));
  $("image_suggestions").replaceChildren(...(r.suggestions.length ? r.suggestions.map((s) => {
    const row = el("div", undefined, "suggest-row");
    row.append(el("span", LABELS[s.attribute] || s.attribute, "label"));
    if (s.hint) row.append(el("span", s.hint, "muted"));
    for (const opt of s.options) {
      const b = el("button", `add ${(LABELS[s.attribute] || s.attribute).toLowerCase()}: ${opt}`, "chip");
      b.type = "button";
      b.addEventListener("click", () => { accepted.add(`${s.attribute}:${opt}`); $("form").requestSubmit(); });
      row.append(b);
    }
    return row;
  }) : [el("span", "None: your prompt covers every attribute.", "muted")]));
  $("image_accepted").replaceChildren(...(r.accepted.length ? r.accepted.map((a) => {
    const [attr, value] = a.split(/:(.*)/s);
    const b = el("button", `${(LABELS[attr] || attr).toLowerCase()}: ${value} ✕`, "chip accepted");
    b.type = "button"; b.title = "Remove";
    b.addEventListener("click", () => { accepted.delete(a); $("form").requestSubmit(); });
    return b;
  }) : [el("span", "Nothing yet.", "muted")]));
  $("image_rules").replaceChildren(...r.rules.map((x) => { const li = el("li"); li.append(el("strong", x.code), " " + x.what); return li; }));
}

function render(r) {
  last = r;
  $("image_result").hidden = true;
  $("result").hidden = false;
  $("tabs").replaceChildren(...["gpt", "gemini", "claude"].map((t) => {
    const b = el("button", LABELS[t] + (t === r.target ? " (selected)" : ""));
    b.type = "button"; b.dataset.target = t; b.setAttribute("role", "tab");
    b.addEventListener("click", () => showTarget(t));
    return b;
  }));
  showTarget(r.target);

  const a = r.stage_a, c = r.category;
  $("category_line").textContent =
    `Category used: ${LABELS[c.used] || c.used} (${c.source === "user" ? "your choice" : c.source === "stage_c" ? "chosen by Stage C" : "detected"}). ` +
    `Stage A predicted ${LABELS[a.category] || a.category} with confidence ${a.confidence.toFixed(2)}.`;
  $("disagreement").hidden = !c.disagreement;
  $("disagreement").textContent = c.disagreement
    ? `You chose ${LABELS[c.used]}, but Stage A predicted ${LABELS[c.stage_a] || c.stage_a}. Your choice was used.` : "";

  $("uncertain").hidden = !c.uncertain;
  if (c.uncertain) {
    $("uncertain_text").textContent = `The category is uncertain: Stage A was unsure (${LABELS[a.category] || a.category}, ` +
      `${a.confidence.toFixed(2)}). Stage C suggests ${LABELS[c.guess] || c.guess}; please confirm or pick another.`;
    $("pick").value = c.guess;
  }

  $("issues").replaceChildren(...(r.issues.length ? r.issues.map((i) => el("li", `${i.code}: ${i.issue}`))
                                                  : [el("li", "No issues found.", "muted")]));
  $("rules").replaceChildren(...(r.rules.length ? r.rules.map((x) => {
    const li = el("li"); li.append(el("strong", x.code), " " + x.what); return li;
  }) : [el("li", "No rule changed the prompt.", "muted")]));
  $("unresolved").textContent = r.unresolved_after_b.length ? "Left for Stage C / you: " + r.unresolved_after_b.join("; ") : "";

  renderCodingTests(r.coding_tests, null);

  const s = r.stage_c;
  let text;
  if (!s.routed) text = "Not needed: Stage B resolved everything Stage C could fix.";
  else if (!s.available) text = `Needed (${s.reasons.join("; ")}), but Stage C is not installed; Stage B's result is shown.`;
  else if (s.accepted) text = `Used: filled ${s.fields.join(", ")} in ${s.seconds}s.` +
    (s.category_status === "uncertain" ? " Its category is only a suggestion; please confirm it above." : "");
  else text = `Tried, but its answer was rejected (${s.errors.join("; ")}); Stage B's result is shown.`;
  $("stage_c").textContent = text;
  $("stage_c_raw").hidden = !s.raw;
  $("stage_c_raw").textContent = s.raw || "";
}

function renderCodingTests(ct, generated) {
  $("coding_panel").hidden = !ct;
  if (!ct) return;
  const t = generated || ct.tests;
  $("coding_tests").hidden = !t;
  $("gen_tests").hidden = !!t || !ct.can_generate;
  if (t) {
    const lines = t.mode === "stdout"
      ? ["# The program's output must equal the reference output:", ...(t.expected_stdout || "").split("\n")]
      : [t.signature ? `# expected: ${t.signature}` : `# function under test: ${t.function}`, ...t.tests];
    $("coding_tests").textContent = lines.join("\n");
    $("coding_note").textContent = (t.validated ? "VALIDATED. " : "") + t.note;
  } else {
    $("coding_note").textContent = ct.can_generate
      ? "No validated tests for this prompt (it is not a dataset item). You can generate unvalidated tests."
      : "No validated tests for this prompt, and generating tests needs CEREBRAS_API_KEY.";
  }
}

$("gen_tests").addEventListener("click", async () => {
  $("gen_tests").disabled = true;
  $("status").textContent = "Generating tests...";
  try {
    const resp = await fetch("/api/coding-tests", { method: "POST", headers: { "Content-Type": "application/json" },
                                                    body: JSON.stringify({ optimized_prompt: last.optimized_plain }) });
    if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
    renderCodingTests(last.coding_tests, await resp.json());
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = "Error: " + e.message;
  } finally {
    $("gen_tests").disabled = false;
  }
});

async function loadHistory() {
  const items = await (await fetch("/api/history?limit=15")).json();
  $("history").replaceChildren(...(items.length ? items.map((h) => {
    const li = el("li");
    const b = el("button", h.text, "link"); b.type = "button";
    b.addEventListener("click", async () => {
      const d = await (await fetch(`/api/history/${h.prompt_id}`)).json();
      $("prompt").value = d.original_text;
      const res = d.results[d.results.length - 1];
      if (res) {
        $("status").textContent = `Loaded prompt #${h.prompt_id}: ${res.steps.length} changes, Stage C ${res.used_lora ? "used" : "not used"}.`;
      }
    });
    li.append(b, el("span", " " + new Date(h.created_at).toLocaleString(), "muted"));
    return li;
  }) : [el("li", "No prompts yet.", "muted")]));
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("go").disabled = true;
  $("status").textContent = "Optimizing...";
  const body = {
    prompt: $("prompt").value,
    target: document.querySelector("input[name=target]:checked").value,
    category: $("category").value,
    attachment_type: isImageMode() ? "none" : $("attachment").value,
    attachment_name: $("attachment_name").value || null,
    context: isImageMode() ? null : ($("context").value || null),
    accepted_suggestions: isImageMode() ? [...accepted] : [],
  };
  try {
    const resp = await fetch("/api/optimize", { method: "POST", headers: { "Content-Type": "application/json" },
                                                body: JSON.stringify(body) });
    if (!resp.ok) throw new Error((await resp.json()).detail?.[0]?.msg || resp.statusText);
    const data = await resp.json();
    if (data.mode === "image") renderImage(data); else render(data);
    $("status").textContent = "";
    loadHistory();
  } catch (e) {
    $("status").textContent = "Error: " + e.message;
  } finally {
    $("go").disabled = false;
  }
});

$("repick").addEventListener("click", () => {
  $("category").value = $("pick").value;          // the user's choice overrides Stage A
  $("form").requestSubmit();
});

$("prompt").addEventListener("input", () => { accepted = new Set(); });   // a new request starts clean

$("image_copy").addEventListener("click", async () => {
  const r = last.renderings[shownImage];
  const text = r.prompt + (r.negative_prompt ? "\n\nNegative prompt: " + r.negative_prompt : "");
  try { await navigator.clipboard.writeText(text); $("status").textContent = "Copied."; }
  catch { $("status").textContent = "Copy failed; select the text instead."; }
});

$("copy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(last.renderings[shown]); $("status").textContent = "Copied."; }
  catch { $("status").textContent = "Copy failed; select the text instead."; }
});

init();
