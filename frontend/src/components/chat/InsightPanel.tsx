import { AnimatePresence, motion } from "framer-motion";
import type { SessionTurn } from "../../api/session";

type Props = {
  turn: SessionTurn | undefined;
  open: boolean;
  onClose: () => void;
};

export default function InsightPanel({ turn, open, onClose }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ x: "100%", opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 200 }}
          className="fixed right-0 top-0 h-full w-80 z-50 bg-surface border-l border-border flex flex-col overflow-hidden shadow-2xl"
        >
          <div className="flex items-center justify-between p-4 border-b border-border">
            <span className="text-xs font-semibold uppercase tracking-widest text-accent">Insight</span>
            <button onClick={onClose} className="text-muted hover:text-text p-1">
              x
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {turn?.diagram_svg && (
              <div>
                <p className="text-xs uppercase tracking-widest text-muted mb-2">Concept diagram</p>
                <div
                  className="rounded-lg bg-surface-2 border border-border p-3"
                  dangerouslySetInnerHTML={{ __html: turn.diagram_svg }}
                />
              </div>
            )}
            {turn?.clarification && (
              <div>
                <p className="text-xs uppercase tracking-widest text-muted mb-2">What this probed</p>
                <p className="text-sm text-muted leading-relaxed">{turn.clarification}</p>
              </div>
            )}
            <div>
              <p className="text-xs uppercase tracking-widest text-muted mb-2">The question</p>
              <p className="text-sm text-accent italic leading-relaxed">{turn?.question}</p>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
