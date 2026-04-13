import { apiUrl, parseSSE } from "./client";

export type SessionMode = "socratic" | "exam_prep";

async function readApiError(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) return `HTTP ${response.status}`;
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail;
  } catch {
    // non-JSON response body, return raw text
  }
  return body;
}

export async function startSession(body: {
  concept_id: string;
  user_id?: string | null;
  session_mode?: SessionMode;
  use_stage2?: boolean;
}): Promise<{
  session_id: string;
  user_id: string;
  concept_id: string;
  prompt_version: string;
  opening_question: string;
  session_mode: SessionMode;
  exam_target_turns: number;
  use_stage2: boolean;
  teaching_phase: string | null;
  session_name: string | null;
}> {
  const r = await fetch(apiUrl("/session/start"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type StreamTurnCallbacks = {
  onToken: (t: string) => void;
  onMeta: (meta: Record<string, unknown>) => void;
  onRegenerating: () => void;
  onRevealStart?: () => void;
  onRevealChunk?: (t: string) => void;
  onRevealDone?: (payload: Record<string, unknown>) => void;
};

export async function streamTurn(
  sessionId: string,
  answer: string,
  callbacks: StreamTurnCallbacks
): Promise<void> {
  const r = await fetch(apiUrl(`/session/${sessionId}/turn`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  if (!r.ok) throw new Error(await r.text());
  let acc = "";
  await parseSSE(r, (ev, data) => {
    if (ev === "token") {
      acc += data;
      callbacks.onToken(data);
    }
    if (ev === "regenerating") callbacks.onRegenerating();
    if (ev === "reveal_start") callbacks.onRevealStart?.();
    if (ev === "reveal_chunk") callbacks.onRevealChunk?.(data);
    if (ev === "reveal_done") {
      try {
        callbacks.onRevealDone?.(JSON.parse(data) as Record<string, unknown>);
      } catch {
        callbacks.onRevealDone?.({});
      }
    }
    if (ev === "done") {
      try {
        callbacks.onMeta(JSON.parse(data) as Record<string, unknown>);
      } catch {
        callbacks.onMeta({});
      }
    }
    if (ev === "error") throw new Error(data);
  });
  if (acc && !acc.trim()) callbacks.onMeta({});
}

export interface ExamResult {
  turns_graded: number;
  points_earned: number;
  points_possible: number;
  score_percent: number;
}

export async function endSession(sessionId: string): Promise<{
  session_id: string;
  summary: string | null;
  exam: ExamResult | null;
}> {
  const r = await fetch(apiUrl(`/session/${sessionId}/end`), { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── Session history ─────────────────────────────────────────────────

export interface SessionHistoryItem {
  session_id: string;
  concept_id: string;
  concept_name: string;
  total_turns: number;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  name?: string | null;
}

export async function fetchSessionHistory(
  userId?: string | null,
  conceptId?: string | null
): Promise<SessionHistoryItem[]> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  if (conceptId) params.set("concept_id", conceptId);
  const qs = params.toString();
  const r = await fetch(apiUrl(`/session/history${qs ? `?${qs}` : ""}`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export interface TurnInfo {
  id: string;
  session_id: string;
  student_input: string;
  classifier_state: string;
  question_generated: string;
  created_at: string;
  clarification?: string | null;
  diagram_svg?: string | null;
  clarification_status?: "pending" | "generating" | "ready" | "failed" | null;
}

export async function fetchSessionTurns(sessionId: string): Promise<TurnInfo[]> {
  const r = await fetch(apiUrl(`/session/${sessionId}/turns`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type SessionTurn = {
  turn_id: string;
  student_input: string;
  question: string;
  classifier_state: string;
  clarification: string | null;
  diagram_svg: string | null;
  clarification_status: "pending" | "generating" | "ready" | "failed";
  created_at: string;
};

export async function getSessionTurns(sessionId: string): Promise<SessionTurn[]> {
  const rows = await fetchSessionTurns(sessionId);
  return rows.map((t) => ({
    turn_id: t.id,
    student_input: t.student_input,
    question: t.question_generated,
    classifier_state: t.classifier_state,
    clarification: t.clarification ?? null,
    diagram_svg: t.diagram_svg ?? null,
    clarification_status: (t.clarification_status ?? "pending") as SessionTurn["clarification_status"],
    created_at: t.created_at,
  }));
}

export async function getTurnClarification(turnId: string): Promise<{
  turn_id: string;
  clarification: string | null;
  diagram_svg: string | null;
  status: "pending" | "generating" | "ready" | "failed";
}> {
  const r = await fetch(apiUrl(`/session/turn/${turnId}/clarification`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── Stage 2 ─────────────────────────────────────────────────────────

export interface SessionPhase {
  session_id: string;
  phase: string;
  probe_turns: number;
  max_probe_turns: number;
  self_rating: number | null;
  report_status: string | null;
  last_reveal: Record<string, unknown> | null;
  last_tutor_plain: string | null;
}

export async function fetchSessionPhase(sessionId: string): Promise<SessionPhase> {
  const r = await fetch(apiUrl(`/session/${sessionId}/phase`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function revealEarly(sessionId: string): Promise<SessionPhase> {
  const r = await fetch(apiUrl(`/session/${sessionId}/reveal`), { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function submitReflect(sessionId: string, rating: number): Promise<SessionPhase> {
  const r = await fetch(apiUrl(`/session/${sessionId}/reflect`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (!r.ok) throw new Error(await readApiError(r));
  return r.json();
}

export async function fetchReportStatus(sessionId: string): Promise<{
  session_id: string;
  status: string;
  pdf_path: string | null;
}> {
  const r = await fetch(apiUrl(`/report/${sessionId}/status`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export function reportPdfUrl(sessionId: string): string {
  return apiUrl(`/report/${sessionId}/pdf`);
}

export async function fetchSessionDiagram(sessionId: string, conceptId: string): Promise<string> {
  const r = await fetch(apiUrl(`/session/${sessionId}/diagram/${conceptId}`));
  if (!r.ok) throw new Error(await r.text());
  return r.text();
}

export type ReportSummary = {
  session_id: string;
  status: string;
  analyst: {
    overall_performance?: string;
    strongest_concept?: string;
    weakest_concept?: string;
    insight?: string;
    recommendations?: string[];
    dunning_kruger_flag?: boolean;
    concepts_to_review?: string[];
  };
  review_schedule: Array<{
    concept_name: string;
    days_until: number;
    review_date: string;
    mastery_score: number;
  }>;
  session_name: string | null;
};

export async function fetchReportSummary(sessionId: string): Promise<ReportSummary> {
  const r = await fetch(apiUrl(`/report/${sessionId}/summary`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
