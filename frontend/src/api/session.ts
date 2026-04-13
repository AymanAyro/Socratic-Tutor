import { apiUrl, parseSSE } from "./client";

export type SessionMode = "socratic" | "exam_prep";

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
}

export async function fetchSessionTurns(sessionId: string): Promise<TurnInfo[]> {
  const r = await fetch(apiUrl(`/session/${sessionId}/turns`));
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
  if (!r.ok) throw new Error(await r.text());
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
