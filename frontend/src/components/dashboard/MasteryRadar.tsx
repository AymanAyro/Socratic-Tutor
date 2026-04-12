import { motion } from "framer-motion";

type Item = { concept_id: string; score: number; name?: string };

export default function MasteryRadar({ items }: { items: Item[] }) {
  if (!items.length) {
    return <p className="text-sm text-ink-400">No mastery data yet -- complete a session first.</p>;
  }
  const max = Math.max(...items.map((i) => i.score), 0.01);
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-ink-700">Mastery by concept</h3>
      <ul className="space-y-2.5">
        {items.map((item, i) => (
          <li key={item.concept_id} className="flex items-center gap-3">
            <div className="w-40 truncate text-xs text-ink-500" title={item.name ?? item.concept_id}>
              {item.name ?? item.concept_id.slice(0, 8) + "..."}
            </div>
            <div className="flex-1 h-2 rounded-full bg-mist-100 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-accent to-accent-light"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(100, (item.score / max) * 100)}%` }}
                transition={{ delay: i * 0.06, duration: 0.6, ease: "easeOut" }}
              />
            </div>
            <span className="text-xs tabular-nums w-10 text-right text-ink-500">{item.score.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
