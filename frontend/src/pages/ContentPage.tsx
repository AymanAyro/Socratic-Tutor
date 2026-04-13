import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  deleteAllData,
  fetchConcepts,
  ingestDocumentStream,
  uploadContent,
  type IngestProgress,
} from "../api/content";
import DocumentList from "../components/content/DocumentList";
import IngestProgressBar from "../components/content/IngestProgress";
import ProjectPicker from "../components/content/ProjectPicker";
import FileDropzone from "../components/upload/FileDropzone";
import { useSessionStore } from "../stores/sessionStore";

export default function ContentPage() {
  const { documentId, setDocumentId, setConceptId, conceptId, projectId } = useSessionStore();
  const [status, setStatus] = useState<string | null>(null);
  const [ingestProgress, setIngestProgress] = useState<IngestProgress | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const qc = useQueryClient();

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadContent(file, projectId),
    onSuccess: (d) => {
      setDocumentId(d.document_id);
      setStatus(`Uploaded "${d.title}". Ready to ingest.`);
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["concepts", d.document_id] });
    },
  });

  const runIngest = async () => {
    if (!documentId) return;
    setIngesting(true);
    setIngestProgress(null);
    setIngestError(null);
    setStatus(null);
    try {
      let conceptsFound = 0;
      let chunksIndexed = 0;
      await ingestDocumentStream(documentId, (p) => {
        setIngestProgress(p);
        if (p.event === "done") {
          chunksIndexed = p.document?.chunk_count ?? 0;
        }
        if (p.step === "kg_done") {
          const match = (p.detail ?? "").match(/(\d+)\s+concepts?/i);
          conceptsFound = match ? Number(match[1]) : 0;
        }
        if (p.event === "error") {
          setIngestError(p.detail ?? "Ingest failed");
        }
      });
      const chunkText = chunksIndexed ? `${chunksIndexed} chunks` : "chunks indexed";
      const conceptText = conceptsFound ? `${conceptsFound} concepts found` : "concept extraction completed";
      setStatus(`✓ Ingested — ${chunkText}, ${conceptText}.`);
      qc.invalidateQueries({ queryKey: ["concepts", documentId] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    } catch (e) {
      setIngestError(e instanceof Error ? e.message : String(e));
    } finally {
      setIngesting(false);
    }
  };

  const resetMut = useMutation({
    mutationFn: () => deleteAllData(),
    onSuccess: () => {
      setDocumentId(null);
      setConceptId(null);
      setStatus("All data erased.");
      qc.invalidateQueries();
    },
  });

  const conceptsQ = useQuery({
    queryKey: ["concepts", documentId],
    queryFn: () => fetchConcepts(documentId!),
    enabled: !!documentId,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink-950">Content</h1>
          <p className="text-sm text-ink-500 mt-1">
            Upload study material, run ingestion, then pick a concept for the tutor.
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          type="button"
          className="rounded-lg border border-red-200 text-red-500 px-3 py-1.5 text-xs font-medium hover:bg-red-50 transition-colors"
          onClick={() => {
            if (confirm("This will delete ALL documents, sessions, and progress data. Are you sure?"))
              resetMut.mutate();
          }}
        >
          Reset all data
        </motion.button>
      </div>

      <ProjectPicker />
      <FileDropzone busy={uploadMut.isPending} onFile={(f) => uploadMut.mutate(f)} />
      {uploadMut.isError && (
        <p className="text-sm text-red-600">{(uploadMut.error as Error).message}</p>
      )}

      <DocumentList />

      {documentId && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              type="button"
              className="rounded-xl bg-gradient-to-r from-accent to-accent-dim text-white px-5 py-2 text-sm font-medium shadow-sm shadow-accent/20 disabled:opacity-40 disabled:shadow-none"
              disabled={!documentId || ingesting}
              onClick={runIngest}
            >
              {ingesting ? "Ingesting..." : "Run ingest"}
            </motion.button>
            <span className="text-xs text-ink-400 font-mono">doc {documentId.slice(0, 8)}...</span>
          </div>

          {(ingesting || ingestProgress || ingestError) && (
            <IngestProgressBar progress={ingestProgress} error={ingestError} />
          )}
        </div>
      )}

      {status && !ingesting && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-sm text-ink-700"
        >
          {status}
        </motion.p>
      )}

      {conceptsQ.data && conceptsQ.data.concepts.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-ink-700 mb-2">Concepts</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {conceptsQ.data.concepts.map((c, i) => (
              <motion.li
                key={c.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04, duration: 0.25 }}
              >
                <button
                  type="button"
                  onClick={() => setConceptId(c.id)}
                  className={`w-full text-left rounded-xl border px-4 py-3 text-sm transition-all duration-200 card-hover ${
                    conceptId === c.id
                      ? "border-accent bg-accent-50 shadow-sm shadow-accent/10"
                      : "border-mist-200 bg-white hover:border-accent/30"
                  }`}
                >
                  <div className="font-medium text-ink-950">{c.name}</div>
                  {c.description && (
                    <div className="text-xs text-ink-500 line-clamp-2 mt-0.5">{c.description}</div>
                  )}
                </button>
              </motion.li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
