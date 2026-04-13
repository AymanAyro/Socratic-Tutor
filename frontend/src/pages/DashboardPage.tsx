import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "../stores/sessionStore";
import { fetchDue, fetchMastery } from "../api/progress";
import { fetchSessionHistory } from "../api/session";
import MasteryRadar from "../components/dashboard/MasteryRadar";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { userId, setUserId, setConceptId } = useSessionStore();

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

  const stats = useMemo(() => {
    const sessions = historyQ.data ?? [];
    const mastery = masteryQ.data ?? [];
    const avgMastery = mastery.length
      ? mastery.reduce((sum, item) => sum + item.score, 0) / mastery.length
      : 0;
    return {
      totalSessions: sessions.length,
      totalConcepts: mastery.length,
      avgMastery,
    };
  }, [historyQ.data, masteryQ.data]);

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
              name: m.concept_name ?? undefined,
              score: m.score,
            }))}
          />
        )}
      </motion.section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-muted">Total sessions</p>
          <p className="text-2xl font-semibold text-text">{stats.totalSessions}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-muted">Concepts studied</p>
          <p className="text-2xl font-semibold text-text">{stats.totalConcepts}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-muted">Average mastery</p>
          <p className="text-2xl font-semibold text-text">{Math.round(stats.avgMastery * 100)}%</p>
        </div>
      </section>

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
                <p className="text-xs text-muted mt-2">{s.total_turns} turns · {s.concept_name}</p>
                <span className="inline-flex mt-2 rounded-md border border-border px-2 py-0.5 text-[11px] text-muted">
                  {s.total_turns >= 5 ? "Progressing" : "Struggling"}
                </span>
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
                <div>
                  <span className="font-medium text-text">{d.name}</span>
                  <div className="h-1.5 bg-surface-2 rounded-full mt-2 overflow-hidden w-36">
                    <div
                      className="h-full bg-accent rounded-full"
                      style={{ width: `${Math.max(0, Math.min(100, (d.score ?? 0) * 100))}%` }}
                    />
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-muted tabular-nums block">{d.next_review_date}</span>
                  <button
                    type="button"
                    className="text-xs text-accent underline mt-1"
                    onClick={() => {
                      setConceptId(d.concept_id);
                      navigate("/tutor");
                    }}
                  >
                    Review now
                  </button>
                </div>
              </motion.li>
            ))}
          </ul>
        )}
      </motion.section>
    </div>
  );
}
