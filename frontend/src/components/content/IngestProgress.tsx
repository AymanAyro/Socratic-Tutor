import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import type { IngestProgress } from "../../api/content";

const STEP_LABELS: Record<string, string> = {
  preflight: "Checking services",
  extracting: "Extracting text",
  kg: "Building concept graph",
  kg_done: "Concept graph ready",
  embedding: "Embedding chunks",
};

export default function IngestProgressBar({
  progress,
  error,
}: {
  progress: IngestProgress | null;
  error: string | null;
}) {
  const [elapsed, setElapsed] = useState(0);
  const t0 = useRef(Date.now());

  useEffect(() => {
    t0.current = Date.now();
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - t0.current) / 1000)), 1000);
    return () => clearInterval(iv);
  }, []);

  if (!progress && !error) return null;

  const pct = progress?.pct ?? 0;
  const step = progress?.step ?? "";
  const label = STEP_LABELS[step] || step;
  const detail = progress?.detail ?? "";
  const isDone = progress?.event === "done";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-mist-200 bg-white/80 p-4 space-y-3 shadow-sm"
    >
      <div className="flex items-center justify-between text-sm">
        <AnimatePresence mode="wait">
          <motion.span
            key={error ? "err" : isDone ? "done" : step}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className={`font-medium ${error ? "text-red-600" : isDone ? "text-green-600" : "text-ink-950"}`}
          >
            {error ? "Ingestion failed" : isDone ? "Ingestion complete" : label}
          </motion.span>
        </AnimatePresence>
        <span className="text-ink-400 tabular-nums text-xs">{elapsed}s</span>
      </div>

      <div className="h-2 w-full rounded-full bg-mist-100 overflow-hidden relative">
        <motion.div
          className={`h-full rounded-full ${
            error ? "bg-red-500" : isDone ? "bg-green-500" : "bg-gradient-to-r from-accent to-accent-light"
          }`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(pct, 100)}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
        {!isDone && !error && (
          <div className="absolute inset-0 overflow-hidden rounded-full">
            <div
              className="h-full w-1/2 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        )}
      </div>

      <p className="text-xs text-ink-500">
        {error || detail}
        {progress?.batch && !isDone && (
          <span className="ml-2 text-ink-400">
            batch {progress.batch}/{progress.total_batches}
          </span>
        )}
      </p>
    </motion.div>
  );
}
