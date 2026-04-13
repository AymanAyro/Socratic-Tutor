const PHASE_STYLES: Record<string, string> = {
  PROBE: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  REVEAL: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  REFLECT: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  CONSOLIDATE: "bg-green-500/10 text-green-400 border-green-500/30",
  END: "bg-gray-500/10 text-gray-400 border-gray-500/30",
};

const PHASE_LABELS: Record<string, string> = {
  PROBE: "Exploration",
  REVEAL: "Reveal",
  REFLECT: "Reflect",
  CONSOLIDATE: "Check",
  END: "Done",
};

export default function PhaseBadge({ phase }: { phase: string }) {
  const style = PHASE_STYLES[phase] ?? PHASE_STYLES.END;
  return (
    <span
      className={`text-xs px-2.5 py-0.5 rounded-full border font-medium uppercase tracking-wider ${style}`}
    >
      {PHASE_LABELS[phase] ?? "Done"}
    </span>
  );
}
