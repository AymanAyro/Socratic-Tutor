import { motion, AnimatePresence } from "framer-motion";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
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
import RevealPanel from "../components/chat/RevealPanel";
import SessionPhaseBar from "../components/chat/SessionPhaseBar";
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

const DISPLAY_LABELS: Record<string, string> = {
  correct: "Got it",
  partial: "Getting there",
  wrong: "Incorrect",
  stuck: "Still working on it",
};

/** Lets React commit `typing` and paint before we await network/SSE (avoids instant hide). */
function yieldToPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

const MIN_TYPING_INDICATOR_MS = 500;

export default function TutorPage() {
  const navigate = useNavigate();
  const {
    conceptId,
    sessionId,
    sessionName,
    messages,
    userId,
    setUserId,
    setConceptId,
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
  const [phaseMeta, setPhaseMeta] = useState<{ probe_turns: number; max_probe_turns: number } | null>(null);
  const [revealContent, setRevealContent] = useState<{
    idealAnswer: string;
    diagramSvg: string | null;
    conceptId: string | null;
  } | null>(null);
  const [reportReadyUrl, setReportReadyUrl] = useState<string | null>(null);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [insightPanelOpen, setInsightPanelOpen] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [showRevealDivider, setShowRevealDivider] = useState(false);
  const [resumedSession, setResumedSession] = useState(false);
  const [resumeBannerDismissed, setResumeBannerDismissed] = useState(false);
  const [phaseHydrated, setPhaseHydrated] = useState(false);
  const [phaseHydrateError, setPhaseHydrateError] = useState(false);
  const [typingEpoch, setTypingEpoch] = useState(0);
  const typingStartedAtRef = useRef(0);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

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
      setConceptId(String(data.concept_id));
      setActiveMode(data.session_mode);
      setExamLive(null);
      setExamFinal(null);
      setLastClassState(null);
      setStage2Active(!!data.use_stage2);
      setTeachingPhase(data.teaching_phase ?? (data.use_stage2 ? "PROBE" : null));
      setRevealContent(null);
      setPhaseMeta(null);
      setReportReadyUrl(null);
      setShowRevealDivider(false);
      setSendError(null);
      setResumedSession(false);
      setResumeBannerDismissed(false);
      setPhaseHydrateError(false);
      try {
        localStorage.setItem("st_use_stage2", String(!!data.use_stage2));
        localStorage.setItem("st_session_mode", data.session_mode);
        const ph = data.teaching_phase ?? (data.use_stage2 ? "PROBE" : "");
        if (ph) localStorage.setItem("st_teaching_phase", ph);
      } catch {
        /* ignore */
      }
      appendMessage({ role: "tutor", text: data.opening_question });
    },
  });

  const endMut = useMutation({
    mutationFn: async (sid: string) => endSession(sid),
    onSuccess: async (data, sid) => {
      if (data.exam) setExamFinal(data.exam);
      if (stage2Active) {
        navigate(`/report/${sid}`);
        return;
      }
      try {
        const st = await fetchReportStatus(sid);
        if (st.status === "ready") setReportReadyUrl(reportPdfUrl(sid));
      } catch {
        /* ignore */
      }
    },
  });

  const canSendFreeText =
    !stage2Active || !sessionId || teachingPhase === "PROBE" || teachingPhase === "CONSOLIDATE";

  const blockedPhaseHint =
    stage2Active && sessionId && !canSendFreeText
      ? teachingPhase === "REFLECT"
        ? "Use the reflection rating (1-5) above to continue."
        : teachingPhase === "REVEAL"
          ? "Review the model answer and click Got it to continue."
          : "Wait for the next step in this phase."
      : null;

  const send = async (text: string) => {
    if (!sessionId || !canSendFreeText) return;
    appendMessage({ role: "student", text });
    typingStartedAtRef.current = Date.now();
    setTypingEpoch((n) => n + 1);
    setTyping(true);
    setRegen(false);
    setSendError(null);
    await yieldToPaint();
    let tutorStarted = false;
    let revealMode = false;
    let responseStarted = false;
    const markResponseStarted = () => {
      if (!responseStarted) {
        responseStarted = true;
        const elapsed = Date.now() - typingStartedAtRef.current;
        const rest = Math.max(0, MIN_TYPING_INDICATOR_MS - elapsed);
        window.setTimeout(() => setTyping(false), rest);
      }
    };
    try {
      await streamTurn(sessionId, text, {
        onToken: (chunk) => {
          if (chunk.length > 0) markResponseStarted();
          if (!revealMode) {
            if (!tutorStarted && chunk.trim().length > 0) {
              tutorStarted = true;
              appendMessage({ role: "tutor", text: "" });
            }
            if (tutorStarted) appendTutorChunk(chunk);
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
          markResponseStarted();
          revealMode = true;
          setShowRevealDivider(true);
          appendMessage({ role: "tutor", text: "" });
        },
        onRevealChunk: (c) => {
          if (c.length > 0) markResponseStarted();
          appendTutorChunk(c);
        },
        onRevealDone: (payload) => {
          const rev = payload.reveal as Record<string, unknown> | undefined;
          setRevealContent({
            idealAnswer: String(rev?.ideal_answer ?? ""),
            diagramSvg: typeof rev?.concept_diagram_svg === "string" ? rev.concept_diagram_svg : null,
            conceptId: typeof rev?.concept_id === "string" ? rev.concept_id : null,
          });
          if (typeof payload.phase === "string") setTeachingPhase(payload.phase as string);
        },
      });
      if (stage2Active) {
        try {
          const ph = await fetchSessionPhase(sessionId);
          setTeachingPhase(ph.phase);
          setPhaseMeta({ probe_turns: ph.probe_turns, max_probe_turns: ph.max_probe_turns });
          if (ph.last_reveal?.ideal_answer) {
            setRevealContent({
              idealAnswer: String(ph.last_reveal.ideal_answer ?? ""),
              diagramSvg:
                typeof ph.last_reveal.concept_diagram_svg === "string"
                  ? ph.last_reveal.concept_diagram_svg
                  : null,
              conceptId:
                typeof ph.last_reveal.concept_id === "string" ? ph.last_reveal.concept_id : null,
            });
          }
        } catch {
          /* ignore */
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch tutor response.";
      setSendError(message);
      appendMessage({ role: "tutor", text: `I hit a temporary issue: ${message}` });
      if (message.includes("does not accept a free-text answer")) {
        try {
          const ph = await fetchSessionPhase(sessionId);
          setTeachingPhase(ph.phase);
          setPhaseMeta({ probe_turns: ph.probe_turns, max_probe_turns: ph.max_probe_turns });
          if (ph.last_reveal?.ideal_answer) {
            setRevealContent({
              idealAnswer: String(ph.last_reveal.ideal_answer ?? ""),
              diagramSvg:
                typeof ph.last_reveal.concept_diagram_svg === "string"
                  ? ph.last_reveal.concept_diagram_svg
                  : null,
              conceptId: typeof ph.last_reveal.concept_id === "string" ? ph.last_reveal.concept_id : null,
            });
          } else {
            setRevealContent(null);
          }
        } catch {
          /* ignore */
        }
      }
    } finally {
      if (!responseStarted) {
        const elapsed = Date.now() - typingStartedAtRef.current;
        const rest = Math.max(0, MIN_TYPING_INDICATOR_MS - elapsed);
        if (rest > 0) {
          await new Promise((r) => setTimeout(r, rest));
        }
        setTyping(false);
      }
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

  useEffect(() => {
    if (sessionId && messages.length > 0) {
      setResumedSession(true);
    }
  }, [sessionId, messages.length]);

  /** Reload: restore Stage 2 phase + UI from API (stage2Active was false, so phase was never fetched before). */
  useEffect(() => {
    if (!sessionId) {
      setPhaseHydrated(false);
      setPhaseHydrateError(false);
      setActiveMode(null);
      return;
    }

    const storedMode = localStorage.getItem("st_session_mode");
    if (storedMode === "socratic" || storedMode === "exam_prep") {
      setActiveMode(storedMode);
    }

    let cancelled = false;
    setPhaseHydrated(false);
    setPhaseHydrateError(false);

    (async () => {
      try {
        const ph = await fetchSessionPhase(sessionId);
        if (cancelled) return;
        setStage2Active(true);
        setTeachingPhase(ph.phase);
        setPhaseMeta({ probe_turns: ph.probe_turns, max_probe_turns: ph.max_probe_turns });
        try {
          localStorage.setItem("st_use_stage2", "true");
          localStorage.setItem("st_teaching_phase", ph.phase);
        } catch {
          /* ignore */
        }
        if (ph.phase === "REVEAL" && ph.last_reveal && String(ph.last_reveal.ideal_answer ?? "").trim()) {
          setRevealContent({
            idealAnswer: String(ph.last_reveal.ideal_answer ?? ""),
            diagramSvg:
              typeof ph.last_reveal.concept_diagram_svg === "string" ? ph.last_reveal.concept_diagram_svg : null,
            conceptId: typeof ph.last_reveal.concept_id === "string" ? ph.last_reveal.concept_id : null,
          });
        } else if (ph.phase !== "REVEAL") {
          setRevealContent(null);
        }
        if (ph.report_status === "ready") {
          setReportReadyUrl(reportPdfUrl(sessionId));
        }
        setPhaseHydrated(true);
      } catch {
        if (cancelled) return;
        const wasStage2 = localStorage.getItem("st_use_stage2") === "true";
        const fallbackPhase = localStorage.getItem("st_teaching_phase");
        if (wasStage2) {
          setStage2Active(true);
          if (fallbackPhase) setTeachingPhase(fallbackPhase);
          setPhaseHydrateError(true);
        } else {
          setStage2Active(false);
          setTeachingPhase(null);
          setPhaseMeta(null);
        }
        setPhaseHydrated(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (!stage2Active || !teachingPhase) return;
    try {
      localStorage.setItem("st_teaching_phase", teachingPhase);
    } catch {
      /* ignore */
    }
  }, [stage2Active, teachingPhase]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, typing, regen, lastClassState]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-text">Tutor</h1>
        <p className="text-sm text-muted mt-1">
          Guided questions only — upload material and choose a concept on the Content tab.
        </p>
      </div>

      {!conceptId && !sessionId && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm px-4 py-3"
        >
          Select a concept from the Content page before starting.
        </motion.div>
      )}
      {sessionId && !conceptId && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl bg-sky-500/10 border border-sky-500/25 text-sky-200 text-sm px-4 py-3"
        >
          Session is active but the selected concept was not found in this browser&apos;s storage (e.g. after clearing
          site data). You can keep going if the chat still works; open{" "}
          <strong className="text-text">Content</strong> and pick the concept again before starting a new session.
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
              title={
                m === "socratic"
                  ? "Guided questioning to build understanding."
                  : "Socratic questions with scoring for exam practice."
              }
              aria-label={m === "socratic" ? "Socratic mode" : "Exam prep mode"}
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
        <div className="space-y-2">
          <SessionPhaseBar
            phase={teachingPhase}
            probeTurns={phaseMeta?.probe_turns}
            maxProbeTurns={phaseMeta?.max_probe_turns}
          />
          {teachingPhase === "PROBE" && (
            <button
              type="button"
              className="underline text-accent hover:text-accent/80 text-xs"
              onClick={async () => {
                if (!sessionId) return;
                try {
                  const ph = await revealEarly(sessionId);
                  setTeachingPhase(ph.phase);
                  if (ph.last_reveal?.ideal_answer) {
                    setRevealContent({
                      idealAnswer: String(ph.last_reveal.ideal_answer ?? ""),
                      diagramSvg:
                        typeof ph.last_reveal.concept_diagram_svg === "string"
                          ? ph.last_reveal.concept_diagram_svg
                          : null,
                      conceptId:
                        typeof ph.last_reveal.concept_id === "string"
                          ? ph.last_reveal.concept_id
                          : null,
                    });
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
            Finish Session
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
              setStage2Active(false);
              setTeachingPhase(null);
              setPhaseMeta(null);
              setRevealContent(null);
              setReportReadyUrl(null);
              setExamLive(null);
              setExamFinal(null);
              setLastClassState(null);
              setShowRevealDivider(false);
              setSendError(null);
              setResumedSession(false);
              setResumeBannerDismissed(false);
              setPhaseHydrateError(false);
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
      {sendError && <p className="text-sm text-red-600">{sendError}</p>}
      {resumedSession && !resumeBannerDismissed && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 flex flex-wrap items-center justify-between gap-2">
          <span>Loaded your saved chat from this browser. Phase and controls sync from the server when online.</span>
          <button
            type="button"
            className="shrink-0 text-emerald-900 underline font-medium hover:opacity-80"
            onClick={() => setResumeBannerDismissed(true)}
          >
            Dismiss
          </button>
        </div>
      )}
      {sessionId && phaseHydrated && phaseHydrateError && stage2Active && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Could not sync session phase from the server. Check your connection and refresh. If this persists, your saved
          phase ({localStorage.getItem("st_teaching_phase") ?? "unknown"}) is shown so you can try reflection or finish
          when the API is back.
        </p>
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

      {revealContent && sessionId && teachingPhase === "REVEAL" && (
        <RevealPanel
          sessionId={sessionId}
          conceptId={revealContent.conceptId}
          idealAnswer={revealContent.idealAnswer}
          diagramSvg={revealContent.diagramSvg}
          isActive={teachingPhase === "REVEAL"}
          onGotIt={() => {
            setTeachingPhase("REFLECT");
            setRevealContent(null);
          }}
        />
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
          {showRevealDivider && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 px-3 py-1.5 text-xs font-medium text-emerald-800 text-center">
              ── Concept Revealed ──
            </div>
          )}
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
          <AnimatePresence>
            {typing && <TypingIndicator key={typingEpoch} />}
          </AnimatePresence>
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
                Understanding: {DISPLAY_LABELS[lastClassState] ?? lastClassState}
              </span>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {stage2Active && sessionId && teachingPhase === "REFLECT" && (
          <div className="mt-3 rounded-xl border border-accent/40 bg-accent/10 p-3 text-sm shrink-0">
            <p className="text-text font-medium mb-1">Reflection</p>
            <p className="text-muted text-xs mb-2">
              Free text is turned off here. Rate how well you understood this concept (1–5). After that you can answer
              the consolidation question in the chat, then use <strong className="text-text">Finish Session</strong> to
              build the PDF report.
            </p>
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-semibold hover:border-accent min-w-[2.5rem]"
                  onClick={async () => {
                    if (!sessionId) return;
                    try {
                      const ph = await submitReflect(sessionId, n);
                      setTeachingPhase(ph.phase);
                      setPhaseMeta({ probe_turns: ph.probe_turns, max_probe_turns: ph.max_probe_turns });
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

        <div className="mt-4">
          <InputBar onSend={send} disabled={!sessionId || typing || !canSendFreeText} />
          {blockedPhaseHint && <p className="mt-2 text-xs text-muted">{blockedPhaseHint}</p>}
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
