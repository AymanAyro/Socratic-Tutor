import type { SessionTurn } from "../../api/session";

type Props = {
  text: string;
  turn?: SessionTurn;
  onInsightClick: (turnId: string) => void;
};

export default function TutorMessage({ text, turn, onInsightClick }: Props) {
  const status = turn?.clarification_status;
  const hasInsight = !!turn && status === "ready";
  const loading = status === "pending" || status === "generating";

  return (
    <div className="flex justify-start">
      <div className="relative max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed bg-surface border border-border text-text shadow-sm">
        <div className="text-[10px] uppercase tracking-wider mb-1 text-accent font-semibold">Tutor</div>
        <div className="whitespace-pre-wrap">{text}</div>
        {hasInsight && (
          <button
            onClick={() => onInsightClick(turn.turn_id)}
            className="absolute -bottom-3 right-3 text-xs px-2.5 py-1 rounded-full bg-accent/10 border border-accent/30 text-accent hover:bg-accent/20 transition-all"
          >
            Insight
          </button>
        )}
        {loading && <div className="absolute -bottom-3 right-3 text-xs px-2.5 py-1 text-muted">...</div>}
      </div>
    </div>
  );
}
