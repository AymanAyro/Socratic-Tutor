import { apiUrl, parseSSE } from "./client";

export type SessionMode = "socratic" | "exam_prep";

export async function startSession(body: {
  concept_id: string;
  user_id?: string | null;
  session_mode?: SessionMode;
}): Promise<{
  session_id: string;
  user_id: string;
  concept_id: string;
  prompt_version: string;
  opening_question: string;
  session_mode: SessionMode;
  exam_target_turns: number;
}> {
  const r = await fetch(apiUrl("/session/start"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function streamTurn(
  sessionId: string,
  answer: string,
  onToken: (t: string) => void,
  onMeta: (meta: Record<string, unknown>) => void,
  onRegenerating: () => void
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
      onToken(data);
    }
    if (ev === "regenerating") onRegenerating();
    if (ev === "done") {
      try {
        onMeta(JSON.parse(data) as Record<string, unknown>);
      } catch {
        onMeta({});
      }
    }
    if (ev === "error") throw new Error(data);
  });
  if (acc && !acc.trim()) onMeta({});
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
