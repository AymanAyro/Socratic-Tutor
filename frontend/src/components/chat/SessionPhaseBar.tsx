const PHASES = ["PROBE", "REVEAL", "REFLECT", "CONSOLIDATE", "END"] as const;

const PHASE_CONFIG: Record<(typeof PHASES)[number], { label: string; description: string }> = {
  PROBE: {
    label: "Exploration",
    description: "Answer the tutor's questions in your own words",
  },
  REVEAL: {
    label: "Reveal",
    description: "See the full explanation and concept diagram",
  },
  REFLECT: {
    label: "Reflect",
    description: "Rate how well you understood this concept",
  },
  CONSOLIDATE: {
    label: "Check",
    description: "One final question to confirm it landed",
  },
  END: {
    label: "Done",
    description: "Session complete - your report is ready",
  },
};

type Props = {
  phase: string;
  probeTurns?: number;
  maxProbeTurns?: number;
};

export default function SessionPhaseBar({ phase, probeTurns, maxProbeTurns }: Props) {
  const activeIdx = Math.max(0, PHASES.indexOf((phase as (typeof PHASES)[number]) || "PROBE"));
  const activeKey = PHASES[activeIdx] || "PROBE";

  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="flex flex-wrap gap-2">
        {PHASES.map((step, idx) => {
          const isDone = idx < activeIdx;
          const isActive = idx === activeIdx;
          return (
            <div
              key={step}
              className={`rounded-full border px-3 py-1 text-xs ${
                isActive
                  ? "border-accent bg-accent/10 text-accent"
                  : isDone
                    ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                    : "border-border bg-surface-2 text-muted"
              }`}
            >
              <span className="mr-1">{isDone ? "[x]" : idx + 1}.</span>
              {PHASE_CONFIG[step].label}
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-muted">{PHASE_CONFIG[activeKey].description}</p>
      {activeKey === "PROBE" && typeof probeTurns === "number" && typeof maxProbeTurns === "number" && (
        <p className="text-xs text-muted mt-1">
          Question {Math.max(1, probeTurns)} of {Math.max(1, maxProbeTurns)}
        </p>
      )}
    </div>
  );
}
