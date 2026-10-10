// Typed client for the FastAPI backend. Every error becomes an ApiError with a message that says what to do.

export type Target = "gpt" | "gemini" | "claude";
export type ImageTarget = "dalle" | "nano_banana" | "stable_diffusion";
export type Category =
  | "auto" | "closed_qa" | "information_extraction" | "classification" | "summarization" | "coding"
  | "image_generation";
export type Attachment = "none" | "image" | "pdf" | "pptx" | "docx" | "spreadsheet" | "code" | "other";

export interface OptimizeRequest {
  prompt: string;
  target: Target | ImageTarget;
  category: Category;
  attachment_type: Attachment;
  attachment_name?: string | null;
  context?: string | null;
  accepted_suggestions?: string[];
}

export interface TokenCount { tokens: number; method: string; exact: boolean }

/** A likely typo: offsets into the prompt as it was sent; suggestions best first. Nothing is changed by the server. */
export interface Typo { word: string; start: number; end: number; suggestions: string[] }

export interface Rule { code: string; what: string; before: string; after: string }

export interface CodingTests {
  source?: string; validated: boolean; item?: string; mode: "function" | "stdout"; function?: string;
  signature?: string; tests: string[]; expected_stdout?: string | null; note: string;
}

export interface OptimizeResult {
  prompt_id: number;
  stage_a: {
    category: string; confidence: number; scores: Record<string, number>; has_context: boolean;
    format_evidence: string[]; constraints_present: string[];
  };
  category: {
    used: string; source: string; requested: string; stage_a: string; disagreement: boolean;
    uncertain: boolean; guess: string | null;
  };
  issues: { code: string; issue: string }[];
  rules: Rule[];
  unresolved_after_b: string[];
  stage_c: {
    available: boolean; routed: boolean; reasons: string[]; used: boolean; accepted: boolean; fields: string[];
    errors: string[]; seconds: number | null; category_status: string | null; raw: string | null;
  };
  unresolved: string[];
  spelling?: Typo[];
  ir: Record<string, unknown>;
  optimized_plain: string;
  renderings: Record<Target, string>;
  tokens: Record<Target, TokenCount>;
  target: Target;
  coding_tests: { tests: CodingTests | null; can_generate: boolean } | null;
}

export interface ImageSuggestion { attribute: string; options: string[]; hint?: string | null }
export interface ImageRendering { prompt: string; negative_prompt?: string | null; params: Record<string, string> }
export interface ImageResult {
  mode: "image"; version: string; prompt_id: number; target: ImageTarget; pii_redactions: number; spelling?: Typo[];
  stated: Record<string, string[]>; avoid_user: string[]; auto_added: { what: string; value: string }[];
  accepted: string[]; suggestions: ImageSuggestion[]; aspect_ratio: string | null;
  rules: Rule[]; ir: Record<string, unknown>; renderings: Record<ImageTarget, ImageRendering>;
}

export interface Options {
  targets: Target[]; image_targets: ImageTarget[]; categories: Category[]; attachment_types: Attachment[];
  stage_c: { available: boolean; model: string | null; device: string | null };
  retention_days: number; compare_enabled: boolean; spelling_available?: boolean;
}

export interface CompareModel {
  id: string; label: string; provider: string; family: string; available: boolean; reason: string | null;
}

export interface Variant {
  answer: string; input_tokens: number; output_tokens: number; reasoning_tokens?: number; total_tokens: number;
  latency_ms: number; finish_reason?: string; cached?: boolean; prompt?: string;
}
export interface TestOutcome { outcome: string; passed: number; total: number; status?: string; detail?: string }
export interface CompareResult {
  prompt_id: number;
  category: OptimizeResult["category"];
  rendered_for: Target; answered_by: string; answered_by_label: string; stand_in: boolean; label: string;
  settings: { temperature: number; max_tokens: number; reasoning_effort?: string | null };
  original: Variant; optimized: Variant;
  change_pct: { input_tokens: number | null; output_tokens: number | null; total_tokens: number | null };
  latency_change_pct: number | null;
  tests: ({ item?: string; validated: boolean; note?: string; original?: TestOutcome; optimized?: TestOutcome }) | null;
  judge: { model: string; blind: boolean; original?: { score: number; reason: string };
           optimized?: { score: number; reason: string } } | null;
}

export interface Provider {
  id: string; label: string; provider: string; family: string; available: boolean; reason: string | null;
  key_env: string; usage_24h: { requests: number; tokens: number; limit_tokens: number | null } | null;
}
export interface Status {
  providers: Provider[];
  stage_c: Options["stage_c"];
  coding_tests: { can_generate: boolean; sandbox: string };
  retention_days: number;
}

export interface Example {
  id: string; title: string; kind: string; category: Category; target: Target | ImageTarget; prompt: string;
  context?: string; attachment_type?: Attachment; why: string; demo?: boolean;
}

export interface Table { headers: string[]; rows: string[][]; bold: boolean[] }
export interface Section { id: string; title: string; level: number; intro: string[]; bullets: string[]; tables: Table[] }
export interface SuiteModel {
  id: string; label: string; available: boolean; reason: string | null; has_results: boolean;
  summary: { n: number; vague: number; optimized: number; only_optimized: number; only_vague: number;
             mcnemar_p: number; mean_reduction: number | null } | null;
}
export interface Results {
  source: string; token_source: string;
  tokens: { reduction_pct: number; ci_low: number; ci_high: number; n: number; input_before?: number;
            input_after?: number; output_before?: number; output_after?: number; cost_more?: number;
            cost_more_pct?: number } | null;
  sections: Section[];
  suite: { generated: string | null; models: SuiteModel[] };
}

export type CaseStatus = "fixed" | "hurt" | "both" | "neither";
export interface SuiteGrid {
  categories: string[]; models: SuiteModel[]; generated: string | null;
  cases: { id: string; category: string; scenario: string; difficulty: string[]; vague_prompt: string }[];
  verdicts: Record<string, Record<string, { vague: boolean; optimized: boolean; status: CaseStatus;
                                             tokens: { vague: number; optimized: number } }>>;
}
export interface SuiteVerdict {
  answer: string; correct: boolean; method: string; why: string | null; input_tokens: number;
  output_tokens: number; total_tokens: number; latency_ms: number;
}
export interface SuiteCase {
  case: { id: string; category: string; scenario: string; difficulty: string[]; material: string; vague_prompt: string };
  gold: string; notes: string;
  prompts: { vague: string; optimized: string; rendered_for: string };
  pipeline: { stage_a: { category: string; confidence: number }; category_used: string; rules: string[];
              routed: boolean; stage_c: unknown };
  model: { id: string; label: string }; live: boolean;
  result: ({ vague: SuiteVerdict; optimized: SuiteVerdict; total_reduction_pct: number | null }) | null;
}

export interface HistoryItem {
  prompt_id: number; text: string; created_at: string; expires_at: string; mode: "text" | "image";
  category: string | null; category_source: string | null; target: string | null; attachment: string | null;
  changes: number; used_stage_c: boolean; optimized: string | null;
  compares: { model: string; target: string; original_total: number; optimized_total: number }[];
}
export interface HistoryDetail {
  prompt_id: number; original_text: string; pii_redactions: number; expires_at: string;
  features: Record<string, unknown> | null;
  results: { result_id: number; optimized_text: string; ir: Record<string, unknown>; used_lora: boolean;
             steps: { step: number; stage: string; rule: string | null; before: string; after: string; note: string | null }[];
             renderings: Record<string, string> }[];
}
export interface CompareHistoryItem {
  prompt_id: number; text: string; model: string; target: string; created_at: string;
  original: { input: number; output: number | null; total: number };
  optimized: { input: number; output: number | null; total: number };
  change_pct: number | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function friendly(status: number, detail: string): string {
  if (status === 429) {
    return detail.toLowerCase().includes("groq")
      ? `Groq's daily quota is used up. Switch the model to gpt-oss-120b on Cerebras and run again. (${detail})`
      : `This model's daily quota is used up. Pick another model and run again. (${detail})`;
  }
  if (status === 503) return detail.includes(".env") ? `${detail} Then restart the server.` : detail;
  if (status === 404) return detail || "Not found.";
  if (status === 422) return `The server rejected the input: ${detail}`;
  return detail || `The server answered ${status}.`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, "Can't reach the PromptOpt server. Start it with `uvicorn app.api:app` in backend/ and try again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail
        : Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : detail;
    } catch { /* not JSON */ }
    throw new ApiError(res.status, friendly(res.status, detail));
  }
  return res.json() as Promise<T>;
}

const post = <T,>(url: string, body: unknown) =>
  request<T>(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  options: () => request<Options>("/api/options"),
  status: () => request<Status>("/api/ui/status"),
  examples: () => request<{ examples: Example[] }>("/api/ui/examples"),
  tokens: (text: string, signal?: AbortSignal) =>
    request<Record<Target, TokenCount>>("/api/ui/tokens", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal }),
  optimize: (req: OptimizeRequest) => post<OptimizeResult | ImageResult>("/api/optimize", req),
  codingTests: (optimized_prompt: string) => post<CodingTests>("/api/coding-tests", { optimized_prompt }),
  compareModels: () => request<{ default: string | null; models: CompareModel[] }>("/api/compare/models"),
  compare: (req: OptimizeRequest & { model: string; judge: boolean }) => post<CompareResult>("/api/compare", req),
  compareHistory: () => request<CompareHistoryItem[]>("/api/ui/compare-history"),
  results: () => request<Results>("/api/ui/results"),
  suiteGrid: () => request<SuiteGrid>("/api/ui/suite-grid"),
  suiteCase: (id: string, model: string) =>
    request<SuiteCase>(`/api/suite/${encodeURIComponent(id)}?model=${encodeURIComponent(model)}`),
  suiteRun: (id: string, model: string) => post<SuiteCase>(`/api/suite/${encodeURIComponent(id)}/run`, { model }),
  history: (q = "", limit = 50, offset = 0) =>
    request<{ total: number; items: HistoryItem[] }>(
      `/api/ui/history?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`),
  historyItem: (id: number) => request<HistoryDetail>(`/api/history/${id}`),
  deleteHistory: (id: number) => request<{ deleted: number }>(`/api/ui/history/${id}`, { method: "DELETE" }),
};
