import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchSessionHistory, fetchSessionTurns, type SessionHistoryItem, type TurnInfo } from "../../api/session";
import { useSessionStore } from "../../stores/sessionStore";
import ChatBubble from "../chat/ChatBubble";

function TurnViewer({ sessionId }: { sessionId: string }) {
  const turnsQ = useQuery({
    queryKey: ["turns", sessionId],
    queryFn: () => fetchSessionTurns(sessionId),
  });

  if (turnsQ.isLoading) return <p className="text-xs text-ink-400 p-2">Loading turns...</p>;
  if (!turnsQ.data?.length) return <p className="text-xs text-ink-400 p-2">No turns recorded.</p>;

  return (
    <div className="space-y-2 p-2 max-h-64 overflow-y-auto">
      {turnsQ.data.map((t: TurnInfo) => (
        <div key={t.id} className="space-y-1">
          <ChatBubble role="student" text={t.student_input} />
          <ChatBubble role="tutor" text={t.question_generated} />
        </div>
      ))}
    </div>
  );
}

export default function SessionHistory() {
  const { userId } = useSessionStore();
  const [expanded, setExpanded] = useState<string | null>(null);

  const historyQ = useQuery({
    queryKey: ["session-history", userId],
    queryFn: () => fetchSessionHistory(userId),
    enabled: !!userId,
  });

  if (!userId) return null;
  if (historyQ.isLoading) return <p className="text-sm text-ink-400">Loading history...</p>;
  if (!historyQ.data?.length) return <p className="text-sm text-ink-400">No past sessions.</p>;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-ink-700">Past Sessions</h3>
      <ul className="space-y-1.5">
        {historyQ.data.map((s: SessionHistoryItem, i: number) => (
          <motion.li
            key={s.session_id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04, duration: 0.2 }}
          >
            <button
              type="button"
              onClick={() => setExpanded(expanded === s.session_id ? null : s.session_id)}
              className="w-full text-left rounded-xl border border-mist-200 bg-white px-4 py-2.5 text-sm transition-all duration-200 hover:border-accent/30 hover:shadow-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink-950">{s.concept_name}</span>
                <span className="text-xs text-ink-400 bg-mist-100 px-2 py-0.5 rounded-full">{s.total_turns} turns</span>
              </div>
              <div className="text-xs text-ink-500 mt-0.5">
                {new Date(s.started_at).toLocaleDateString()}{" "}
                <span className={s.ended_at ? "text-green-600" : "text-amber-500"}>
                  {s.ended_at ? "completed" : "active"}
                </span>
              </div>
            </button>
            <AnimatePresence>
              {expanded === s.session_id && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden mt-1 ml-3 border-l-2 border-accent/20 pl-3"
                >
                  <TurnViewer sessionId={s.session_id} />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
