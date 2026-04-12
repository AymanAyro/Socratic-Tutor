import { apiUrl, parseSSE } from "./client";

export interface DocumentInfo {
  id: string;
  title: string;
  source_type: string;
  chunk_count: number;
  ingested_at: string;
  project_id: string | null;
}

export async function uploadContent(
  file: File,
  projectId?: string | null
): Promise<{ document_id: string; title: string; source_type: string }> {
  const fd = new FormData();
  fd.append("file", file);
  if (projectId) fd.append("project_id", projectId);
  const r = await fetch(apiUrl("/content/upload"), { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export interface IngestProgress {
  event: string;
  step?: string;
  detail?: string;
  pct?: number;
  batch?: number;
  total_batches?: number;
  document?: DocumentInfo;
}

export async function ingestDocumentStream(
  documentId: string,
  onProgress: (p: IngestProgress) => void
): Promise<void> {
  const r = await fetch(apiUrl(`/content/ingest/${documentId}`), { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  await parseSSE(r, (_ev, data) => {
    try {
      const parsed = JSON.parse(data) as IngestProgress;
      onProgress(parsed);
      if (parsed.event === "error") {
        throw new Error(parsed.detail ?? "Ingest failed");
      }
    } catch (e) {
      if (e instanceof SyntaxError) return;
      throw e;
    }
  });
}

export async function fetchDocuments(
  projectId?: string | null
): Promise<DocumentInfo[]> {
  const params = projectId ? `?project_id=${projectId}` : "";
  const r = await fetch(apiUrl(`/content/documents${params}`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const r = await fetch(apiUrl(`/content/document/${documentId}`), { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
}

export async function deleteAllData(): Promise<void> {
  const r = await fetch(apiUrl("/content/all"), { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
}

export async function fetchConcepts(documentId: string): Promise<{
  document_id: string;
  concepts: { id: string; name: string; description: string | null }[];
  edges: unknown[];
}> {
  const r = await fetch(apiUrl(`/content/concepts/${documentId}`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── Projects ──────────────────────────────────────────────────────

export interface ProjectInfo {
  id: string;
  name: string;
  created_at: string;
}

export async function fetchProjects(): Promise<ProjectInfo[]> {
  const r = await fetch(apiUrl("/projects"));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function createProject(name: string): Promise<ProjectInfo> {
  const r = await fetch(apiUrl("/projects"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const r = await fetch(apiUrl(`/projects/${projectId}`), { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
}
