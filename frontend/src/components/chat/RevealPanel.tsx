import { useEffect, useState } from "react";
import { fetchSessionDiagram } from "../../api/session";

type Props = {
  sessionId: string;
  conceptId: string | null;
  idealAnswer: string;
  diagramSvg: string | null;
  isActive: boolean;
  onGotIt: () => void;
};

export default function RevealPanel({
  sessionId,
  conceptId,
  idealAnswer,
  diagramSvg,
  isActive,
  onGotIt,
}: Props) {
  const [svg, setSvg] = useState<string | null>(diagramSvg);
  const [loading, setLoading] = useState(!diagramSvg);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setSvg(diagramSvg);
    setUnavailable(false);
    if (!isActive || diagramSvg || !conceptId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const maxAttempts = 10;
    let attempts = 0;
    const timer = setInterval(async () => {
      attempts += 1;
      try {
        const result = await fetchSessionDiagram(sessionId, conceptId);
        if (!cancelled && result.trim()) {
          setSvg(result);
          setLoading(false);
          clearInterval(timer);
          return;
        }
      } catch {
        // Ignore transient fetch failures until max attempts are reached.
      }
      if (attempts >= maxAttempts && !cancelled) {
        setLoading(false);
        setUnavailable(true);
        clearInterval(timer);
      }
    }, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [sessionId, conceptId, diagramSvg, isActive]);

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-4">
      <div>
        <h3 className="font-semibold text-text">Model answer</h3>
        <p className="text-sm text-muted mt-1 whitespace-pre-wrap">{idealAnswer}</p>
      </div>
      <div>
        <h3 className="font-semibold text-text">Concept diagram</h3>
        {loading && (
          <div className="mt-2 h-44 rounded-lg border border-border bg-surface-2 animate-pulse flex items-center justify-center text-sm text-muted">
            Building your concept diagram...
          </div>
        )}
        {!loading && svg && (
          <div
            className="mt-2 rounded-lg border border-border bg-surface-2 p-2 overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        )}
        {!loading && !svg && unavailable && (
          <p className="mt-2 text-sm text-muted">Diagram unavailable</p>
        )}
      </div>
      <button
        type="button"
        className="rounded-lg bg-accent text-white px-3 py-2 text-sm font-medium"
        onClick={onGotIt}
      >
        Got it
      </button>
    </div>
  );
}
