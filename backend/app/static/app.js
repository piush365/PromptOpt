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

function fmtTokens(v) {
  return `in ${v.input_tokens}, out ${v.output_tokens}` + (v.reasoning_tokens ? ` (reasoning ${v.reasoning_tokens})` : "") +
    `, total ${v.total_tokens}; ${(v.latency_ms / 1000).toFixed(1)} s` + (v.cached ? " (cached)" : "") +
    (v.finish_reason === "length" ? "; cut off at the token limit" : "");
}

function pct(x) { return x === null || x === undefined ? "-" : (x > 0 ? "+" : "") + x + "%"; }

function testLine(t) {
  if (!t) return "";
  if (!t.validated) return t.note;
  const r = (v) => `${v.outcome} (${v.passed}/${v.total})`;
  return `Sandbox tests (dataset item ${t.item}, validated on the reference): original ${r(t.original)}, ` +
    `optimized ${r(t.optimized)}.`;
}

function renderCompare(c) {
  $("compare_result").hidden = false;
  $("compare_label").textContent = c.label + `. Same model, temperature ${c.settings.temperature}, max ${c.settings.max_tokens} tokens` +
    (c.settings.reasoning_effort ? `, reasoning ${c.settings.reasoning_effort}` : "") + ".";
  $("compare_summary").textContent = `Optimized vs original: input tokens ${pct(c.change_pct.input_tokens)}, ` +
    `output ${pct(c.change_pct.output_tokens)}, total ${pct(c.change_pct.total_tokens)}, latency ${pct(c.latency_change_pct)}.`;
  for (const v of ["original", "optimized"]) {
    $(`cmp_${v}_answer`).textContent = c[v].answer || "(empty answer)";
    $(`cmp_${v}_meta`).textContent = fmtTokens(c[v]);
  }
  $("compare_tests").textContent = testLine(c.tests);
  const j = c.judge;
  $("compare_judge_line").textContent = j ? `Blind judge (${j.model}, never told which prompt produced which answer): ` +
    `original ${j.original?.score ?? "-"}/10 (${j.original?.reason ?? ""}); optimized ${j.optimized?.score ?? "-"}/10 ` +
    `(${j.optimized?.reason ?? ""}).` : "";
}

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
  $("compare_controls").hidden = image;
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
  const cm = await (await fetch("/api/compare/models")).json();
  $("compare_model").replaceChildren(...cm.models.map((m) => {
    const o = el("option", m.label + (m.available ? "" : " (needs API key)")); o.value = m.id;
    o.disabled = !m.available; o.title = m.reason || ""; o.selected = m.id === cm.default;
    return o;
  }));
  $("compare").disabled = !cm.default;
  $("compare").title = cm.default ? "Run the original and the optimized prompt on the chosen model" :
    "No model available: add an API key to backend/.env";
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

$("compare").addEventListener("click", async () => {
  if (isImageMode()) { $("status").textContent = "Compare runs text prompts only."; return; }
  if (!$("prompt").value.trim()) { $("status").textContent = "Enter a prompt first."; return; }
  $("compare").disabled = true;
  $("status").textContent = "Comparing (two calls; Cerebras paces calls about 25 s apart)...";
  const body = {
    prompt: $("prompt").value,
    target: document.querySelector("input[name=target]:checked").value,
    category: $("category").value,
    attachment_type: $("attachment").value,
    attachment_name: $("attachment_name").value || null,
    context: $("context").value || null,
    model: $("compare_model").value,
    judge: $("compare_judge").checked,
  };
  try {
    const resp = await fetch("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" },
                                               body: JSON.stringify(body) });
    const data = await resp.json();
    if (!resp.ok) throw new Error(typeof data.detail === "string" ? data.detail : resp.statusText);
    renderCompare(data);
    $("status").textContent = "";
    loadHistory();
  } catch (e) {
    $("status").textContent = "Compare: " + e.message;
  } finally {
    $("compare").disabled = false;
  }
});

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

// ---------------------------------------------------------------- Test suite (correctness suite)
let SUITE = null;

function verdict(span, ok) {
  span.textContent = ok === null ? "" : (ok ? "✅ correct" : "❌ wrong");
  span.className = "verdict " + (ok === null ? "" : ok ? "ok" : "bad");
}

function suiteHeadline() {
  const m = SUITE.models.find((x) => x.id === $("suite_model").value);
  const s = m && m.summary;
  $("suite_headline").textContent = !s ? `No stored results for ${m ? m.label : "this model"}; use "Run live".` :
    `${m.label}: vague prompt correct on ${s.vague}/${s.n}, optimized on ${s.optimized}/${s.n} ` +
    `(fixed by optimizing: ${s.only_optimized}, broken: ${s.only_vague}; McNemar p = ${s.mcnemar_p.toFixed(3)}); ` +
    `total tokens ${pct(s.mean_reduction === null ? null : -s.mean_reduction)} per case on average. ` +
    "Full report: evaluation/correctness_suite/RESULTS.md";
}

function renderSuite(d) {
  $("suite_scenario").textContent = `${LABELS[d.case.category] || d.case.category}: ${d.case.scenario}. ` +
    `Difficulty: ${d.case.difficulty.join(", ")}.` + (d.notes ? ` Why: ${d.notes}` : "");
  $("suite_material").textContent = d.case.material;
  $("suite_vague_prompt").textContent = d.case.vague_prompt;
  $("suite_opt_prompt").textContent = d.prompts.optimized;
  const p = d.pipeline;
  $("suite_opt_note").textContent = `(${d.prompts.rendered_for.toUpperCase()} rendering; Stage A: ` +
    `${p.stage_a.category} ${p.stage_a.confidence.toFixed(2)}; rules ${p.rules.map((r) => r.split("_")[0]).join(", ")}` +
    (p.routed ? "; Stage C" : "") + ")";
  $("suite_gold").textContent = d.gold;
  const r = d.result;
  for (const [v, key] of [["vague", "vague"], ["opt", "optimized"]]) {
    const x = r && r[key];
    $(`suite_${v}_answer`).textContent = x ? x.answer : "(not run yet: press \"Run live\")";
    verdict($(`suite_${v}_mark`), x ? x.correct : null);
    $(`suite_${v}_meta`).textContent = x ? `tokens in ${x.input_tokens}, out ${x.output_tokens}, total ${x.total_tokens}; ` +
      `${(x.latency_ms / 1000).toFixed(1)} s; scored by ${x.method}` + (x.why ? `. Why wrong: ${x.why}` : "") : "";
  }
  $("suite_tokens").textContent = r ? `Total tokens: ${r.vague.total_tokens} -> ${r.optimized.total_tokens} ` +
    `(${pct(r.total_reduction_pct === null ? null : -r.total_reduction_pct)}) on ${d.model.label}` +
    (d.live ? " (run live)" : " (stored result)") : "";
}

async function loadSuiteCase(live = false) {
  const id = $("suite_case").value, model = $("suite_model").value;
  $("suite_status").textContent = live ? "Running both prompts on the model ..." : "";
  $("suite_live").disabled = true;
  try {
    const res = live ? await fetch(`/api/suite/${encodeURIComponent(id)}/run`, {method: "POST",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({model})})
      : await fetch(`/api/suite/${encodeURIComponent(id)}?model=${encodeURIComponent(model)}`);
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || res.statusText);
    renderSuite(d);
    $("suite_status").textContent = "";
  } catch (e) {
    $("suite_status").textContent = "Error: " + e.message;
  } finally {
    const m = SUITE.models.find((x) => x.id === model);
    $("suite_live").disabled = !(m && m.available);
    $("suite_live").title = m && !m.available ? m.reason : "Run both prompts on this model now (cached answers are reused)";
  }
}

async function initSuite() {
  SUITE = await (await fetch("/api/suite")).json();
  $("suite_case").replaceChildren(...SUITE.categories.map((cat) => {
    const g = document.createElement("optgroup"); g.label = LABELS[cat] || cat;
    g.replaceChildren(...SUITE.cases.filter((c) => c.category === cat).map((c) => {
      const o = el("option", `${c.id}: ${c.scenario}`); o.value = c.id; return o;
    }));
    return g;
  }));
  $("suite_model").replaceChildren(...SUITE.models.map((m) => {
    const o = el("option", m.label + (m.has_results ? "" : m.available ? " (no stored results)" : " (needs API key)"));
    o.value = m.id; o.disabled = !m.has_results && !m.available; return o;
  }));
  suiteHeadline();
  loadSuiteCase();
}

function stepCase(d) {
  const s = $("suite_case"); s.selectedIndex = (s.selectedIndex + d + s.options.length) % s.options.length;
  loadSuiteCase();
}

$("suite_box").addEventListener("toggle", () => { if ($("suite_box").open && !SUITE) initSuite(); });
$("suite_case").addEventListener("change", () => loadSuiteCase());
$("suite_model").addEventListener("change", () => { suiteHeadline(); loadSuiteCase(); });
$("suite_live").addEventListener("click", () => loadSuiteCase(true));
$("suite_prev").addEventListener("click", () => stepCase(-1));
$("suite_next").addEventListener("click", () => stepCase(1));

init();
