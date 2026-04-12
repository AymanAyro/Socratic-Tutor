import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useSessionStore } from "../stores/sessionStore";
import { fetchDue, fetchMastery } from "../api/progress";
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

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink-950">Dashboard</h1>
          <p className="text-sm text-ink-500 mt-1">Mastery estimates and spaced repetition due list.</p>
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
        <p className="text-xs font-mono text-ink-400">
          Learner: <span className="select-all text-ink-600">{userId}</span>
        </p>
      )}

      {!userId && (
        <motion.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm text-ink-500"
        >
          Start a tutor session or create a learner ID to see progress.
        </motion.p>
      )}

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-2xl border border-mist-200 bg-white/80 p-5 shadow-sm card-hover"
      >
        {masteryQ.isLoading && <p className="text-sm text-ink-400">Loading mastery...</p>}
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
        transition={{ delay: 0.1 }}
        className="rounded-2xl border border-mist-200 bg-white/80 p-5 shadow-sm card-hover"
      >
        <h2 className="text-sm font-semibold text-ink-700 mb-3">Due for review</h2>
        {dueQ.isLoading && <p className="text-sm text-ink-400">Loading...</p>}
        {dueQ.data && !dueQ.data.length && (
          <p className="text-sm text-ink-400">Nothing due today.</p>
        )}
        {dueQ.data && dueQ.data.length > 0 && (
          <ul className="space-y-2 text-sm">
            {dueQ.data.map((d, i) => (
              <motion.li
                key={d.concept_id}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04, duration: 0.2 }}
                className="flex justify-between gap-4 border-b border-mist-100 pb-2"
              >
                <span className="font-medium text-ink-950">{d.name}</span>
                <span className="text-ink-400 tabular-nums">{d.next_review_date}</span>
              </motion.li>
            ))}
          </ul>
        )}
      </motion.section>
    </div>
  );
}
