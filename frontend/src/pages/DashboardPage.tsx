import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useSessionStore } from "../stores/sessionStore";
import { fetchDue, fetchMastery } from "../api/progress";
import { fetchSessionHistory } from "../api/session";
import MasteryRadar from "../components/dashboard/MasteryRadar";

export default function DashboardPage() {
  const { userId, setUserId } = useSessionStore();

  const masteryQ = useQuery({
    queryKey: ["mastery", userId],
    queryFn: () => fetchMastery(userId!),
    enabled: !!userId,
  });

  const dueQ = useQuery({
    queryKey: ["due", userId],
    queryFn: () => fetchDue(userId!),
    enabled: !!userId,
  });

  const historyQ = useQuery({
    queryKey: ["session-history", userId],
    queryFn: () => fetchSessionHistory(userId!),
    enabled: !!userId,
  });

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-border bg-surface p-5">
        <div>
          <h1 className="text-2xl font-semibold text-text">Welcome back</h1>
          <p className="text-sm text-muted mt-1">
            You have {dueQ.data?.length ?? 0} concepts due for review.
          </p>
        </div>
        {!userId && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            className="rounded-xl bg-gradient-to-r from-ink-800 to-ink-900 text-white px-5 py-2 text-sm font-medium shadow-sm"
            onClick={() => setUserId(crypto.randomUUID())}
          >
            Create learner ID
          </motion.button>
        )}
      </div>

      {userId && (
        <p className="text-xs font-mono text-muted">
          Learner: <span className="select-all text-text">{userId}</span>
        </p>
      )}

      {!userId && (
        <motion.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm text-muted"
        >
          Start a tutor session or create a learner ID to see progress.
        </motion.p>
      )}

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-2xl border border-border bg-surface p-5 shadow-sm card-hover"
      >
        {masteryQ.isLoading && <p className="text-sm text-muted">Loading mastery...</p>}
        {masteryQ.data && (
          <MasteryRadar
            items={masteryQ.data.map((m) => ({
              concept_id: m.concept_id,
              score: m.score,
            }))}
          />
        )}
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="rounded-2xl border border-border bg-surface p-5 shadow-sm card-hover"
      >
        <h2 className="text-sm font-semibold text-text mb-3">Recent sessions</h2>
        {historyQ.isLoading && <p className="text-sm text-muted">Loading session history...</p>}
        {historyQ.data && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {historyQ.data.slice(0, 6).map((s) => (
              <div key={s.session_id} className="rounded-xl border border-border p-3 bg-surface-2">
                <p className="text-sm font-medium text-text">{s.name ?? s.concept_name}</p>
                <p className="text-xs text-muted mt-1">{new Date(s.started_at).toLocaleDateString()}</p>
                <p className="text-xs text-muted mt-2">{s.total_turns} turns</p>
              </div>
            ))}
          </div>
        )}
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-2xl border border-border bg-surface p-5 shadow-sm card-hover"
      >
        <h2 className="text-sm font-semibold text-text mb-3">Due for review</h2>
        {dueQ.isLoading && <p className="text-sm text-muted">Loading...</p>}
        {dueQ.data && !dueQ.data.length && (
          <p className="text-sm text-muted">Nothing due today.</p>
        )}
        {dueQ.data && dueQ.data.length > 0 && (
          <ul className="space-y-2 text-sm">
            {dueQ.data.map((d, i) => (
              <motion.li
                key={d.concept_id}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04, duration: 0.2 }}
                className="flex justify-between gap-4 border-b border-border pb-2"
              >
                <span className="font-medium text-text">{d.name}</span>
                <span className="text-muted tabular-nums">{d.next_review_date}</span>
              </motion.li>
            ))}
          </ul>
        )}
      </motion.section>
    </div>
  );
}
