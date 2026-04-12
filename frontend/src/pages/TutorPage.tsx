import { motion, AnimatePresence } from "framer-motion";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { endSession, startSession, streamTurn, type ExamResult, type SessionMode } from "../api/session";
import ChatBubble from "../components/chat/ChatBubble";
import InputBar from "../components/chat/InputBar";
import TypingIndicator from "../components/chat/TypingIndicator";
import SessionHistory from "../components/session/SessionHistory";
import { useSessionStore } from "../stores/sessionStore";

type ExamLiveMeta = {
  turnScore: number;
  average: number;
  turnIndex: number;
  target: number;
};

export default function TutorPage() {
  const {
    conceptId,
    sessionId,
    messages,
    userId,
    setUserId,
    setSessionId,
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

  const startMut = useMutation({
    mutationFn: async () => {
      if (!conceptId) throw new Error("Pick a concept on Content first");
      return startSession({
        concept_id: conceptId,
        user_id: userId,
        session_mode: sessionMode,
      });
    },
    onSuccess: (data) => {
      setUserId(data.user_id);
      resetChat();
      setSessionId(data.session_id);
      setActiveMode(data.session_mode);
      setExamLive(null);
      setExamFinal(null);
      setLastClassState(null);
      appendMessage({ role: "tutor", text: data.opening_question });
    },
  });

  const endMut = useMutation({
    mutationFn: async (sid: string) => endSession(sid),
    onSuccess: (data) => {
      if (data.exam) setExamFinal(data.exam);
    },
  });

  const send = async (text: string) => {
    if (!sessionId) return;
    appendMessage({ role: "student", text });
    setTyping(true);
    setRegen(false);
    let tutorStarted = false;
    try {
      await streamTurn(
        sessionId,
        text,
        (chunk) => {
          if (!tutorStarted) {
            tutorStarted = true;
            appendMessage({ role: "tutor", text: "" });
          }
          appendTutorChunk(chunk);
        },
        (meta) => {
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
        },
        () => setRegen(true)
      );
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-950">Tutor</h1>
        <p className="text-sm text-ink-500 mt-1">
          Guided questions only — upload material and choose a concept on the Content tab.
        </p>
      </div>

      {!conceptId && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl bg-amber-50/80 border border-amber-200/60 text-amber-800 text-sm px-4 py-3"
        >
          Select a concept from the Content page before starting.
        </motion.div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-ink-500 uppercase tracking-wide">Mode</span>
        <div className="flex rounded-xl border border-mist-200 p-0.5 bg-mist-50/50">
          {(["socratic", "exam_prep"] as const).map((m) => (
            <button
              key={m}
              type="button"
              disabled={!!sessionId}
              onClick={() => setSessionMode(m)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                sessionMode === m
                  ? "bg-white text-ink-900 shadow-sm"
                  : "text-ink-500 hover:text-ink-700"
              } ${sessionId ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {m === "socratic" ? "Socratic" : "Exam prep"}
            </button>
          ))}
        </div>
        {sessionMode === "exam_prep" && !sessionId && (
          <p className="text-xs text-ink-500 max-w-md">
            Questions stay Socratic; each answer is scored. Use &quot;Finish &amp; score&quot; for a
            summary.
          </p>
        )}
      </div>

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
            className="rounded-xl border border-mist-200 px-4 py-2 text-sm text-ink-600 hover:bg-mist-50 transition-colors"
            onClick={() => {
              resetChat();
              setSessionId(null);
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
                : "border-mist-200 text-ink-600 hover:border-accent/30"
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
            className="rounded-xl border border-mist-200 bg-white/90 px-4 py-3 text-sm text-ink-700"
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
            <div className="mt-2 h-1.5 rounded-full bg-mist-200 overflow-hidden">
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
            className="rounded-2xl border border-accent/30 bg-gradient-to-br from-accent-50 to-white p-5 shadow-sm"
          >
            <h3 className="text-sm font-semibold text-ink-900">Exam session result</h3>
            <p className="mt-2 text-2xl font-bold text-accent">
              {examFinal.score_percent.toFixed(1)}%
            </p>
            <p className="text-sm text-ink-600 mt-1">
              {examFinal.points_earned.toFixed(2)} / {examFinal.points_possible.toFixed(0)} points
              across {examFinal.turns_graded} graded turn(s).
            </p>
            <button
              type="button"
              className="mt-3 text-xs text-ink-500 underline hover:text-ink-700"
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
            <div className="rounded-2xl border border-mist-200 bg-white/80 p-4 shadow-sm">
              <SessionHistory />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="rounded-2xl border border-mist-200 bg-white/80 shadow-sm p-4 min-h-[320px] flex flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto max-h-[480px] pr-1">
          {messages.map((m) => (
            <ChatBubble key={m.id} role={m.role} text={m.text} />
          ))}
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
    </div>
  );
}
