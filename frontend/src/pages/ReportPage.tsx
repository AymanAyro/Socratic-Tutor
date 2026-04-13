import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { fetchReportStatus, fetchReportSummary, reportPdfUrl } from "../api/session";

export default function ReportPage() {
  const { sessionId } = useParams();
  const sid = sessionId || "";
  const statusQ = useQuery({
    queryKey: ["report-status", sid],
    queryFn: () => fetchReportStatus(sid),
    enabled: !!sid,
    refetchInterval: (q) => (q.state.data?.status === "generating" || q.state.data?.status === "pending" ? 2000 : false),
  });
  const summaryQ = useQuery({
    queryKey: ["report-summary", sid],
    queryFn: () => fetchReportSummary(sid),
    enabled: !!sid,
    refetchInterval: 2000,
  });

  const status = statusQ.data?.status ?? "generating";
  const downloadUrl = useMemo(() => (sid ? reportPdfUrl(sid) : "#"), [sid]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-text">Session Report</h1>
      {(status === "generating" || status === "pending" || status === "none") && (
        <p className="text-sm text-muted">Generating your session report...</p>
      )}
      {status === "ready" && (
        <a
          className="inline-flex rounded-lg bg-accent text-white px-4 py-2 text-sm font-medium"
          href={downloadUrl}
        >
          Download Report
        </a>
      )}

      <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
        <h2 className="font-semibold text-text">Quick summary</h2>
        <p className="text-sm text-muted">{summaryQ.data?.analyst?.insight ?? "Preparing your personalized insight..."}</p>
        {!!summaryQ.data?.analyst?.recommendations?.length && (
          <ul className="text-sm text-muted list-disc pl-5 space-y-1">
            {summaryQ.data.analyst.recommendations.map((item, idx) => (
              <li key={`${idx}-${item}`}>{item}</li>
            ))}
          </ul>
        )}
        {!!summaryQ.data?.review_schedule?.length && (
          <div className="space-y-2">
            {summaryQ.data.review_schedule.map((item) => (
              <div key={`${item.concept_name}-${item.review_date}`} className="rounded-lg border border-border p-2">
                <div className="flex justify-between text-sm">
                  <span>{item.concept_name}</span>
                  <span className="text-muted">Review in {item.days_until} days</span>
                </div>
                <div className="h-1.5 bg-surface-2 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-accent rounded-full" style={{ width: `${Math.max(0, Math.min(100, item.mastery_score * 100))}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
