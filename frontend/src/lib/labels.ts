// Every word the UI shows for a code the backend sends, in plain language.

export const CATEGORY: Record<string, string> = {
  auto: "Auto-detect",
  closed_qa: "Question about a text",
  information_extraction: "Extract information",
  classification: "Classify",
  summarization: "Summarise",
  coding: "Coding",
  other: "Other",
  image_generation: "Image generation",
};

export const CATEGORY_SHORT: Record<string, string> = {
  closed_qa: "Q&A",
  information_extraction: "Extract",
  classification: "Classify",
  summarization: "Summarise",
  coding: "Coding",
  other: "Other",
};

export const TARGET: Record<string, string> = {
  gpt: "GPT", gemini: "Gemini", claude: "Claude",
  dalle: "DALL·E", nano_banana: "Nano Banana", stable_diffusion: "Stable Diffusion",
};

export const ATTACHMENT: Record<string, string> = {
  none: "No attachment", image: "Image", pdf: "PDF", pptx: "Slides (PPTX)", docx: "Word (DOCX)",
  spreadsheet: "Spreadsheet", code: "Code file", other: "Other file",
};

export const IMAGE_ATTR: Record<string, string> = {
  subject_detail: "Subject detail", style: "Style / medium", composition: "Composition", lighting: "Lighting",
  palette: "Colour palette", mood: "Mood", aspect_ratio: "Aspect ratio", background: "Background",
  avoid: "Things to avoid",
};

/** One line per rule: what it does and why, written for someone who has never seen the code. */
export const RULE: Record<string, { name: string; why: string }> = {
  B01: { name: "Remove filler", why: "Words like “hey can you just” cost tokens and say nothing to the model." },
  B02: { name: "Remove repeats", why: "A sentence said twice is paid for twice." },
  B03: { name: "Add an output format", why: "Without a format, models write long answers nobody asked for." },
  B04: { name: "Add a length limit", why: "A length keeps the answer short enough to use." },
  B05: { name: "Name the programming language", why: "Otherwise the model picks one, or writes several." },
  B06: { name: "List the allowed labels", why: "A classifier needs to know which answers are allowed." },
  B07: { name: "Tidy the structure", why: "Material pasted inside the prompt goes into its own block; the task gets a capital and a full stop." },
  B08: { name: "Answer from the text", why: "Stage A could not tell Q&A, extraction and summary apart, so only what they share is added." },
  B09: { name: "Image attachment", why: "Use only what is visible in the image, and say when something isn't visible." },
  B10: { name: "PDF attachment", why: "Answer from the PDF and cite page or section numbers." },
  B11: { name: "Slides attachment", why: "Answer from the slides and refer to them by number." },
  B12: { name: "Word attachment", why: "Answer from the document and cite its section headings." },
  B13: { name: "Other attachment", why: "Answer from the attached file, and say so if it can't be read." },
  B14: { name: "Spreadsheet attachment", why: "Answer from the spreadsheet and name sheets, columns and rows." },
  B15: { name: "Code file attachment", why: "Work on the attached code and point to functions and line numbers." },
  I01: { name: "Clean the request", why: "Drops filler like “please generate an image of” so the subject comes first." },
  I02: { name: "Move “no X” to avoid", why: "“without cars” becomes an avoid item; Stable Diffusion’s positive prompt drops the phrase, since it tends to draw what is named." },
  I12: { name: "Aspect ratio, if implied", why: "Only when your words imply one (“16:9”, “phone wallpaper”, “poster”). No default." },
  I13: { name: "Style first", why: "Stable Diffusion weights early words more, so your style goes to the front." },
  I14: { name: "Safe negatives", why: "The usual negatives (blurry, distorted…), minus any your request conflicts with." },
  I15: { name: "Quality term", why: "A quality phrase that never implies a medium, so your style is kept." },
  I16: { name: "Your suggestions", why: "The suggestion chips you clicked, added in your words." },
};

export function ruleInfo(code: string, fallback = "") {
  const short = code.split("_")[0];
  return { short, ...(RULE[short] ?? { name: code.replace(/^[A-Z0-9]+_/, "").replace(/_/g, " ").toLowerCase(), why: fallback }) };
}

/** Stage A issue codes. */
export const ISSUE: Record<string, { title: string; tip: string }> = {
  A02: { title: "No output format", tip: "The prompt doesn't say what shape the answer should take (a list, one line, a code block…)." },
  A03: { title: "Missing constraint", tip: "Something the model needs to know is not stated: length, language, labels, tone or audience." },
  A04: { title: "Filler", tip: "Words that add tokens but no meaning." },
  A05: { title: "Unclear reference", tip: "“this”, “that text”, “the article”: the model can't tell what it refers to." },
};

export const STAGE = {
  A: { name: "Detect", color: "a", one: "Reads your prompt and works out what kind of task it is and what's missing." },
  B: { name: "Rules", color: "b", one: "Fixes what's missing with small, predictable rules. Every change is logged." },
  C: { name: "Small model", color: "c", one: "A small fine-tuned model fills in only what the rules couldn't." },
  R: { name: "Render", color: "r", one: "Writes the same content in the layout each LLM reads best." },
} as const;

export const GLOSSARY: { term: string; plain: string; more?: string }[] = [
  { term: "Prompt", plain: "The instruction you give an AI model." },
  { term: "Vague prompt", plain: "A short prompt that leaves the model to guess the format, length or meaning. In our data: the “degraded” prompt." },
  { term: "Optimized prompt", plain: "The rewritten prompt: same task, plus what was missing, laid out for the chosen model." },
  { term: "Token", plain: "The unit models read and bill by, roughly ¾ of a word. Fewer tokens means cheaper and faster." },
  { term: "Input / output tokens", plain: "Input is what you send (the prompt). Output is what the model writes back. Total is both." },
  { term: "Reasoning tokens", plain: "Hidden “thinking” some models do before answering. You pay for them, though you don't see them." },
  { term: "Exact vs approx.", plain: "GPT tokens are counted exactly with OpenAI's tokenizer. Claude and Gemini don't publish theirs offline, so we estimate characters ÷ 4." },
  { term: "Category", plain: "The kind of task: question about a text, extraction, classification, summary or coding." },
  { term: "Confidence", plain: "How sure Stage A is about the category, from 0 to 1. Category-specific rules only run at 0.6 or above." },
  { term: "0.6 gate", plain: "Below 0.6 confidence, Stage A is often wrong between similar categories, so only safe, shared rules are applied." },
  { term: "Rule (B01–B15)", plain: "One small, tested change: remove filler, add a format, name a language… Each one is logged with before and after." },
  { term: "Routing", plain: "Sending a prompt on to Stage C. It only happens when the rules leave the category or an unclear reference unresolved." },
  { term: "LoRA", plain: "A cheap way to fine-tune a model by training a small add-on instead of the whole model. Stage C is Qwen2.5-0.5B with a LoRA." },
  { term: "Validation (Stage C)", plain: "Stage C's answer is checked: valid JSON, exactly the requested fields, and it must fix what it was asked to. Otherwise Stage B's result is kept." },
  { term: "Fallback", plain: "When Stage C isn't installed or its answer fails validation, the app quietly uses Stage B's result." },
  { term: "IR", plain: "Intermediate representation: the prompt split into fields (task, context, constraints, format) before it is written out for a model." },
  { term: "Rendering", plain: "Writing the IR out for one model: XML tags for Claude, ### headings for GPT, plain labels for Gemini." },
  { term: "Attachment type", plain: "Tells the optimizer a file comes with the prompt (image, PDF…), so the prompt can refer to it. It is a modifier, not a category." },
  { term: "Stand-in model", plain: "We don't have GPT, Claude or Gemini keys, so gpt-oss-120b (on Groq or Cerebras) answers instead, and the UI says so." },
  { term: "Blind judge", plain: "A second model scores both answers 0–10 without being told which prompt produced which." },
  { term: "Sandbox", plain: "An isolated box (bubblewrap) where generated code runs with no network and limited resources." },
  { term: "pass@1", plain: "Share of coding tasks where the model's first answer passes all tests." },
  { term: "95% CI", plain: "Confidence interval: the range the true average very likely lies in, given our sample." },
  { term: "McNemar p", plain: "A test of whether a before/after difference on the same cases is bigger than chance. Below 0.05 is usually called significant." },
  { term: "Cohen's / Fleiss' kappa", plain: "Agreement between raters beyond chance. It collapses to ~0 when nearly every answer is “yes” (the kappa paradox)." },
  { term: "Gwet's AC1", plain: "An agreement measure that doesn't collapse when one answer dominates. We report it next to kappa." },
  { term: "Macro-F1", plain: "F1 (balance of precision and recall) averaged over categories, each counted equally." },
  { term: "Precision / recall", plain: "Precision: of the times a rule fired, how often it should have. Recall: of the times it should have, how often it did." },
  { term: "Ablation", plain: "Turning parts off to see what each part contributes, e.g. A+B vs A+B+C vs C only." },
  { term: "Freeze", plain: "From tag frozen-for-test, Stage A and B were locked so the final test numbers couldn't be tuned on the test set." },
  { term: "Val / test split", plain: "Val is where everything was tuned. Test was run once at the end, so its numbers are honest." },
  { term: "CLIP score", plain: "How well an image matches a text, measured by the CLIP model. Used to check image mode." },
];

export function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  const v = Number(x.toFixed(digits));
  return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(digits) + "%";
}

export function fmt(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : n.toLocaleString("en-IN");
}
