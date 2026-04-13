import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, fetchDocuments, type DocumentInfo } from "../../api/content";
import { useSessionStore } from "../../stores/sessionStore";

export default function DocumentList() {
  const { documentId, setDocumentId, setConceptId, projectId } = useSessionStore();
  const qc = useQueryClient();

  const docsQ = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => fetchDocuments(projectId),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["concepts"] });
      if (documentId === id) {
        setDocumentId(null);
        setConceptId(null);
      }
    },
  });

  if (docsQ.isLoading) return <p className="text-sm text-ink-500">Loading documents...</p>;
  if (!docsQ.data?.length) return <p className="text-sm text-ink-500">No documents yet. Upload one above.</p>;

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold text-ink-700">Documents</h2>
      <ul className="space-y-1.5">
        {docsQ.data.map((d: DocumentInfo, i: number) => {
          const active = documentId === d.id;
          return (
            <motion.li
              key={d.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04, duration: 0.25 }}
              className="flex items-center gap-2"
            >
              <button
                type="button"
                onClick={() => {
                  setDocumentId(d.id);
                  setConceptId(null);
                }}
                className={`flex-1 text-left rounded-xl border px-4 py-2.5 text-sm transition-all duration-200 ${
                  active
                    ? "border-accent bg-accent-50 text-ink-950 shadow-sm shadow-accent/10"
                    : "border-mist-200 bg-white hover:border-accent/30 hover:shadow-sm text-ink-700"
                }`}
              >
                <span className="font-medium">{d.title}</span>
                <span className="ml-2 text-xs text-ink-400">
                  {d.chunk_count > 0 ? `${d.chunk_count} chunks` : "Ready to ingest"} &middot; {d.source_type}
                </span>
              </button>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                type="button"
                title="Delete document"
                aria-label={`Delete document ${d.title}`}
                onClick={() => {
                  if (confirm(`Delete "${d.title}" and all its data?`))
                    deleteMut.mutate(d.id);
                }}
                className="rounded-lg p-2 text-ink-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </motion.button>
            </motion.li>
          );
        })}
      </ul>
    </div>
  );
}
