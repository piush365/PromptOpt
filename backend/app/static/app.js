// PromptOpt UI: plain JS, no build step. All text from the server is inserted with textContent (never innerHTML).
const $ = (id) => document.getElementById(id);
const LABELS = {
  auto: "Auto-detect", closed_qa: "Question about a text", information_extraction: "Extract information",
  classification: "Classify", summarization: "Summarize", coding: "Coding",
  none: "None", image: "Image", pdf: "PDF", pptx: "Slides (PPTX)", docx: "Word (DOCX)",
  spreadsheet: "Spreadsheet", code: "Code file", other: "Other file",
  claude: "Claude", gpt: "GPT", gemini: "Gemini",
};
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
  fill($("category"), opt.categories);
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

function render(r) {
  last = r;
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

  $("issues").replaceChildren(...(r.issues.length ? r.issues.map((i) => el("li", `${i.code}: ${i.issue}`))
                                                  : [el("li", "No issues found.", "muted")]));
  $("rules").replaceChildren(...(r.rules.length ? r.rules.map((x) => {
    const li = el("li"); li.append(el("strong", x.code), " " + x.what); return li;
  }) : [el("li", "No rule changed the prompt.", "muted")]));
  $("unresolved").textContent = r.unresolved_after_b.length ? "Left for Stage C / you: " + r.unresolved_after_b.join("; ") : "";

  const s = r.stage_c;
  let text;
  if (!s.routed) text = "Not needed: Stage B resolved everything Stage C could fix.";
  else if (!s.available) text = `Needed (${s.reasons.join("; ")}), but Stage C is not installed; Stage B's result is shown.`;
  else if (s.accepted) text = `Used: filled ${s.fields.join(", ")} in ${s.seconds}s.`;
  else text = `Tried, but its answer was rejected (${s.errors.join("; ")}); Stage B's result is shown.`;
  $("stage_c").textContent = text;
  $("stage_c_raw").hidden = !s.raw;
  $("stage_c_raw").textContent = s.raw || "";
}

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
    attachment_type: $("attachment").value,
    attachment_name: $("attachment_name").value || null,
    context: $("context").value || null,
  };
  try {
    const resp = await fetch("/api/optimize", { method: "POST", headers: { "Content-Type": "application/json" },
                                                body: JSON.stringify(body) });
    if (!resp.ok) throw new Error((await resp.json()).detail?.[0]?.msg || resp.statusText);
    render(await resp.json());
    $("status").textContent = "";
    loadHistory();
  } catch (e) {
    $("status").textContent = "Error: " + e.message;
  } finally {
    $("go").disabled = false;
  }
});

$("copy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(last.renderings[shown]); $("status").textContent = "Copied."; }
  catch { $("status").textContent = "Copy failed; select the text instead."; }
});

init();
