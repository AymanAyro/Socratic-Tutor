import { motion, AnimatePresence } from "framer-motion";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  endSession,
  fetchReportStatus,
  fetchSessionPhase,
  getSessionTurns,
  reportPdfUrl,
  revealEarly,
  startSession,
  streamTurn,
  submitReflect,
  type ExamResult,
  type SessionMode,
} from "../api/session";
import ChatBubble from "../components/chat/ChatBubble";
import InsightPanel from "../components/chat/InsightPanel";
import InputBar from "../components/chat/InputBar";
import PhaseBadge from "../components/chat/PhaseBadge";
import TutorMessage from "../components/chat/TutorMessage";
import TypingIndicator from "../components/chat/TypingIndicator";
import SessionHistory from "../components/session/SessionHistory";
import { useSessionStore } from "../stores/sessionStore";

type ExamLiveMeta = {
  turnScore: number;
  average: number;
  turnIndex: number;
  target: number;
};

function stage2PhaseHint(phase: string): string {
  switch (phase) {
    case "PROBE":
      return "You answer in your own words; the tutor keeps asking until you hit the minimum turns or a cap, then you get the model answer.";
    case "REVEAL":
      return "Reference answer (and diagram when available). Next: rate how well you understood.";
    case "REFLECT":
      return "Pick 1–5 to unlock one short question that checks you understood the explanation.";
    case "CONSOLIDATE":
      return "Answer the consolidation question; the arc finishes when your understanding checks out.";
    case "END":
      return "This concept arc is complete. End the session or restart to study again.";
    default:
      return "";
  }
}

function applyRevealDiagram(
  rev: Record<string, unknown> | undefined,
  setRevealHtml: (s: string | null) => void,
  setDiagramNote: (s: string | null) => void
) {
  const svg = rev?.concept_diagram_svg;
  const failed = Boolean(rev?.diagram_failed);
  if (typeof svg === "string" && svg.trim()) {
    setRevealHtml(svg);
    setDiagramNote(null);
    return;
  }
  setRevealHtml(null);
  setDiagramNote(
    failed
      ? "No diagram could be generated for this concept. You still have the full text explanation."
      : "No diagram is available for this concept; rely on the written explanation."
  );
}

export default function TutorPage() {
  const {
    conceptId,
    sessionId,
    sessionName,
    messages,
    userId,
    setUserId,
    setSessionId,
    setSessionName,
    appendMessage,
    appendTutorChunk,
    resetChat,
  } = useSessionStore();
  const [typing, setTyping] = useState(false);
  const [regen, setRegen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [sessionMode, setSessionMode] = useState<SessionMode>("socratic");
  const [activeMode, setActiveMode] = useState<SessionMode | null>(null);
  const [examLive, setExamLive] = useState<ExamLiveMeta | null>(null);
  const [examFinal, setExamFinal] = useState<ExamResult | null>(null);
  const [lastClassState, setLastClassState] = useState<string | null>(null);
  const [useStage2, setUseStage2] = useState(true);
  const [stage2Active, setStage2Active] = useState(false);
  const [teachingPhase, setTeachingPhase] = useState<string | null>(null);
  const [revealHtml, setRevealHtml] = useState<string | null>(null);
  const [diagramNote, setDiagramNote] = useState<string | null>(null);
  const [reportReadyUrl, setReportReadyUrl] = useState<string | null>(null);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [insightPanelOpen, setInsightPanelOpen] = useState(false);

  const turnsQ = useQuery({
    queryKey: ["turns", sessionId],
    queryFn: () => getSessionTurns(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (q) => {
      const rows = q.state.data;
      if (!rows?.length) return 2000;
      const allSettled = rows.every(
        (t) => t.clarification_status === "ready" || t.clarification_status === "failed"
      );
      return allSettled ? false : 2000;
    },
  });

  const startMut = useMutation({
    mutationFn: async () => {
      if (!conceptId) throw new Error("Pick a concept on Content first");
      return startSession({
        concept_id: conceptId,
        user_id: userId,
        session_mode: sessionMode,
        use_stage2: sessionMode === "socratic" && useStage2,
      });
    },
    onSuccess: (data) => {
      setUserId(data.user_id);
      resetChat();
      setSessionId(data.session_id);
      setSessionName(data.session_name);
      setActiveMode(data.session_mode);
      setExamLive(null);
      setExamFinal(null);
      setLastClassState(null);
      setStage2Active(!!data.use_stage2);
      setTeachingPhase(data.teaching_phase ?? (data.use_stage2 ? "PROBE" : null));
      setRevealHtml(null);
      setDiagramNote(null);
      setReportReadyUrl(null);
      appendMessage({ role: "tutor", text: data.opening_question });
    },
  });

  const endMut = useMutation({
    mutationFn: async (sid: string) => endSession(sid),
    onSuccess: async (data, sid) => {
      if (data.exam) setExamFinal(data.exam);
      try {
        const st = await fetchReportStatus(sid);
        if (st.status === "ready") setReportReadyUrl(reportPdfUrl(sid));
      } catch {
        /* ignore */
      }
    },
  });

  const send = async (text: string) => {
    if (!sessionId) return;
    appendMessage({ role: "student", text });
    setTyping(true);
    setRegen(false);
    let tutorStarted = false;
    let revealMode = false;
    try {
      await streamTurn(sessionId, text, {
        onToken: (chunk) => {
          if (!revealMode) {
            if (!tutorStarted) {
              tutorStarted = true;
              appendMessage({ role: "tutor", text: "" });
            }
            appendTutorChunk(chunk);
          }
        },
        onMeta: (meta) => {
          if (typeof meta.classifier_state === "string") {
            setLastClassState(meta.classifier_state);
          }
          if (meta.session_mode === "exam_prep" && typeof meta.exam_turn_score === "number") {
            setExamLive({
              turnScore: meta.exam_turn_score as number,
              average: (meta.exam_average_score as number) ?? 0,
              turnIndex: (meta.exam_turn_index as number) ?? 0,
              target: (meta.exam_target_turns as number) ?? 5,
            });
          }
          if (typeof meta.phase === "string") setTeachingPhase(meta.phase as string);
        },
        onRegenerating: () => setRegen(true),
        onRevealStart: () => {
          revealMode = true;
          appendMessage({ role: "tutor", text: "" });
        },
        onRevealChunk: (c) => {
          appendTutorChunk(c);
        },
        onRevealDone: (payload) => {
          const rev = payload.reveal as Record<string, unknown> | undefined;
          applyRevealDiagram(rev, setRevealHtml, setDiagramNote);
          if (typeof payload.phase === "string") setTeachingPhase(payload.phase as string);
        },
      });
      if (stage2Active) {
        try {
          const ph = await fetchSessionPhase(sessionId);
          setTeachingPhase(ph.phase);
          if (ph.last_reveal) {
            applyRevealDiagram(ph.last_reveal as Record<string, unknown>, setRevealHtml, setDiagramNote);
          }
        } catch {
          /* ignore */
        }
      }
    } finally {
      setTyping(false);
    }
  };

  const badgeForState = (state: string) => {
    const colors: Record<string, string> = {
      correct: "bg-emerald-100 text-emerald-800 border-emerald-200",
      partial: "bg-amber-100 text-amber-900 border-amber-200",
      wrong: "bg-rose-100 text-rose-800 border-rose-200",
      stuck: "bg-slate-100 text-slate-700 border-slate-200",
    };
    return colors[state] ?? "bg-mist-100 text-ink-600 border-mist-200";
  };

  const turnForTutorMessage = (text: string) => {
    if (!text.trim()) return undefined;
    return turnsQ.data?.find((t) => t.question.trim() === text.trim());
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-text">Tutor</h1>
        <p className="text-sm text-muted mt-1">
          Guided questions only — upload material and choose a concept on the Content tab.
        </p>
      </div>

      {!conceptId && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm px-4 py-3"
        >
          Select a concept from the Content page before starting.
        </motion.div>
      )}

      {!sessionId && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-border bg-surface p-4">
            <p className="text-sm font-medium">Step 1 — Upload or paste content</p>
            <p className="text-xs text-muted mt-1">
              Use the Content page to upload a document or enter a topic manually.
            </p>
          </div>
          <div className="rounded-xl border border-border bg-surface p-4">
            <p className="text-sm font-medium">Step 2 — Configure session</p>
            <p className="text-xs text-muted mt-1">
              Select concept, choose mode, then start session.
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-muted uppercase tracking-wide">Mode</span>
        <div className="flex rounded-xl border border-border p-0.5 bg-surface">
          {(["socratic", "exam_prep"] as const).map((m) => (
            <button
              key={m}
              type="button"
              disabled={!!sessionId}
              onClick={() => setSessionMode(m)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                sessionMode === m
                  ? "bg-surface-2 text-text shadow-sm"
                  : "text-muted hover:text-text"
              } ${sessionId ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {m === "socratic" ? "Socratic" : "Exam prep"}
            </button>
          ))}
        </div>
        {sessionMode === "exam_prep" && !sessionId && (
          <p className="text-xs text-muted max-w-md">
            Questions stay Socratic; each answer is scored. Use &quot;Finish &amp; score&quot; for a
            summary.
          </p>
        )}
        {sessionMode === "socratic" && !sessionId && (
          <label className="flex items-center gap-2 text-xs text-muted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={useStage2}
              onChange={(e) => setUseStage2(e.target.checked)}
              className="rounded border-mist-300"
            />
            Stage 2 phased session (reveal, reflection, PDF report)
          </label>
        )}
      </div>

      {stage2Active && sessionId && teachingPhase && (
        <div className="text-xs text-muted">
          <p>
            Phase: <span className="font-semibold text-text">{teachingPhase}</span>
          </p>
          {(() => {
            const hint = stage2PhaseHint(teachingPhase);
            return hint ? (
              <p className="mt-1 text-muted leading-snug max-w-2xl">{hint}</p>
            ) : null;
          })()}
          {teachingPhase === "PROBE" && (
            <button
              type="button"
              className="ml-3 underline text-accent hover:text-accent/80"
              onClick={async () => {
                if (!sessionId) return;
                try {
                  const ph = await revealEarly(sessionId);
                  setTeachingPhase(ph.phase);
                  if (ph.last_reveal?.ideal_answer) {
                    appendMessage({
                      role: "tutor",
                      text: String(ph.last_reveal.ideal_answer ?? ""),
                    });
                  }
                  if (ph.last_reveal) {
                    applyRevealDiagram(ph.last_reveal as Record<string, unknown>, setRevealHtml, setDiagramNote);
                  }
                } catch (e) {
                  appendMessage({
                    role: "tutor",
                    text: (e as Error).message,
                  });
                }
              }}
            >
              Reveal now
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          type="button"
          className="rounded-xl bg-gradient-to-r from-ink-800 to-ink-900 text-white px-5 py-2 text-sm font-medium shadow-sm disabled:opacity-40 disabled:shadow-none"
          disabled={!conceptId || startMut.isPending}
          onClick={() => startMut.mutate()}
        >
          {sessionId ? "Restart session" : "Start session"}
        </motion.button>
        {sessionId && stage2Active && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            className="rounded-xl border border-border px-4 py-2 text-sm text-text"
            disabled={endMut.isPending}
            onClick={() => sessionId && endMut.mutate(sessionId)}
          >
            End &amp; report
          </motion.button>
        )}
        {sessionId && activeMode === "exam_prep" && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            className="rounded-xl border border-accent/40 bg-accent-50 text-accent px-4 py-2 text-sm font-medium"
            disabled={endMut.isPending}
            onClick={() => endMut.mutate(sessionId)}
          >
            Finish &amp; score
          </motion.button>
        )}
        {sessionId && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            className="rounded-xl border border-border px-4 py-2 text-sm text-text hover:bg-surface-2 transition-colors"
            onClick={() => {
              resetChat();
              setSessionId(null);
              setSessionName(null);
              setActiveMode(null);
              setExamLive(null);
              setExamFinal(null);
              setLastClassState(null);
            }}
          >
            Clear chat
          </motion.button>
        )}
        {userId && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            className={`rounded-xl border px-4 py-2 text-sm font-medium transition-all duration-200 ${
              showHistory
                ? "border-accent text-accent bg-accent-50 shadow-sm shadow-accent/10"
                : "border-border text-text hover:border-accent/30"
            }`}
            onClick={() => setShowHistory(!showHistory)}
          >
            History
          </motion.button>
        )}
      </div>
      {startMut.isError && (
        <p className="text-sm text-red-600">{(startMut.error as Error).message}</p>
      )}
      {endMut.isError && (
        <p className="text-sm text-red-600">{(endMut.error as Error).message}</p>
      )}

      <AnimatePresence>
        {examLive && activeMode === "exam_prep" && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text"
          >
            <div className="flex flex-wrap gap-4 items-center">
              <span>
                Turn <strong>{examLive.turnIndex}</strong> / {examLive.target}
              </span>
              <span>
                This answer: <strong>{(examLive.turnScore * 100).toFixed(0)}%</strong> of max
              </span>
              <span>
                Running average: <strong>{(examLive.average * 100).toFixed(1)}%</strong>
              </span>
            </div>
            <div className="mt-2 h-1.5 rounded-full bg-surface-2 overflow-hidden">
              <motion.div
                className="h-full bg-accent/80 rounded-full"
                initial={{ width: 0 }}
                animate={{
                  width: `${Math.min(100, (examLive.turnIndex / examLive.target) * 100)}%`,
                }}
                transition={{ duration: 0.35 }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {examFinal && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-2xl border border-accent/30 bg-gradient-to-br from-[#1f1a3b] to-surface p-5 shadow-sm"
          >
            <h3 className="text-sm font-semibold text-text">Exam session result</h3>
            <p className="mt-2 text-2xl font-bold text-accent">
              {examFinal.score_percent.toFixed(1)}%
            </p>
            <p className="text-sm text-muted mt-1">
              {examFinal.points_earned.toFixed(2)} / {examFinal.points_possible.toFixed(0)} points
              across {examFinal.turns_graded} graded turn(s).
            </p>
            <button
              type="button"
              className="mt-3 text-xs text-muted underline hover:text-text"
              onClick={() => setExamFinal(null)}
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showHistory && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
              <SessionHistory />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {reportReadyUrl && (
        <a
          href={reportReadyUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex text-sm text-accent underline"
        >
          Open session report
        </a>
      )}

      {revealHtml && (
        <div
          className="rounded-xl border border-border bg-surface p-3 overflow-x-auto max-h-64 text-sm [&_svg]:max-h-52"
          dangerouslySetInnerHTML={{ __html: revealHtml }}
        />
      )}
      {diagramNote && !revealHtml && (
        <p className="rounded-xl border border-border bg-surface px-3 py-2 text-sm text-muted">{diagramNote}</p>
      )}

      {stage2Active && sessionId && teachingPhase === "REFLECT" && (
        <div className="rounded-xl border border-accent/30 bg-accent/10 p-3 text-sm">
          <p className="text-text mb-2">How well do you feel you understood this concept? (1–5)</p>
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent"
                onClick={async () => {
                  if (!sessionId) return;
                  try {
                    const ph = await submitReflect(sessionId, n);
                    setTeachingPhase(ph.phase);
                    if (ph.last_tutor_plain) {
                      appendMessage({ role: "tutor", text: ph.last_tutor_plain });
                    }
                  } catch (e) {
                    appendMessage({ role: "tutor", text: (e as Error).message });
                  }
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      )}

      <div
        className={`rounded-2xl border border-border bg-surface shadow-sm p-4 min-h-[320px] flex flex-col transition-all duration-300 ${
          insightPanelOpen ? "mr-80" : ""
        }`}
      >
        <div className="border-b border-border px-1 pb-3 mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold">{sessionName ?? "Session"}</h2>
            <p className="text-xs text-muted">
              {activeMode ?? "socratic"} · Turn {turnsQ.data?.length ?? 0}
            </p>
          </div>
          {teachingPhase && <PhaseBadge phase={teachingPhase} />}
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto max-h-[480px] pr-1">
          {messages.map((m) =>
            m.role === "tutor" ? (
              <TutorMessage
                key={m.id}
                text={m.text}
                turn={turnForTutorMessage(m.text)}
                onInsightClick={(turnId) => {
                  setActiveTurnId(turnId);
                  setInsightPanelOpen(true);
                }}
              />
            ) : (
              <ChatBubble key={m.id} role={m.role} text={m.text} />
            )
          )}
          {typing && <TypingIndicator />}
          {regen && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-xs text-accent/70 pl-2"
            >
              Refining question to stay Socratic…
            </motion.p>
          )}
          {lastClassState && sessionId && (
            <div className="pl-2 pt-1">
              <span
                className={`inline-flex items-center rounded-lg border px-2 py-0.5 text-xs font-medium ${badgeForState(lastClassState)}`}
              >
                Understanding: {lastClassState}
              </span>
            </div>
          )}
        </div>
        <div className="mt-4">
          <InputBar onSend={send} disabled={!sessionId || typing} />
        </div>
      </div>
      <InsightPanel
        turn={turnsQ.data?.find((t) => t.turn_id === activeTurnId)}
        open={insightPanelOpen}
        onClose={() => setInsightPanelOpen(false)}
      />
    </div>
  );
}
