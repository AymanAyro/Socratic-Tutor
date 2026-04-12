import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createProject, deleteProject, fetchProjects } from "../../api/content";
import { useSessionStore } from "../../stores/sessionStore";

export default function ProjectPicker() {
  const { projectId, setProjectId } = useSessionStore();
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [showNew, setShowNew] = useState(false);

  const projectsQ = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });

  const createMut = useMutation({
    mutationFn: (name: string) => createProject(name),
    onSuccess: (p) => {
      setProjectId(p.id);
      setNewName("");
      setShowNew(false);
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProject(id),
    onSuccess: (_d, id) => {
      if (projectId === id) setProjectId(null);
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const allItems = [
    { id: null as string | null, name: "All" },
    ...(projectsQ.data?.map((p) => ({ id: p.id as string | null, name: p.name })) ?? []),
  ];

  return (
    <div className="flex flex-wrap items-center gap-1.5 relative">
      {allItems.map((item) => {
        const active = projectId === item.id;
        return (
          <div key={item.id ?? "all"} className="relative flex items-center gap-0.5">
            <button
              type="button"
              onClick={() => setProjectId(item.id)}
              className={`relative z-10 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors duration-200 ${
                active ? "text-white" : "text-ink-600 hover:text-ink-800"
              }`}
            >
              {active && (
                <motion.div
                  layoutId="project-pill"
                  className="absolute inset-0 rounded-lg bg-accent shadow-sm shadow-accent/30"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <span className="relative z-10">{item.name}</span>
            </button>
            {item.id && (
              <button
                type="button"
                title="Delete project"
                onClick={() => {
                  if (confirm(`Delete project "${item.name}" and all its documents?`))
                    deleteMut.mutate(item.id!);
                }}
                className="text-ink-300 hover:text-red-500 p-0.5 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            )}
          </div>
        );
      })}

      {showNew ? (
        <form
          className="flex items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (newName.trim()) createMut.mutate(newName.trim());
          }}
        >
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Project name"
            className="rounded-lg border border-mist-200 px-2.5 py-1 text-xs w-32 focus:border-accent/50 focus:ring-1 focus:ring-accent/20 outline-none transition-all"
          />
          <button type="submit" className="text-accent text-xs font-semibold hover:text-accent-dim" disabled={createMut.isPending}>
            Add
          </button>
          <button type="button" onClick={() => setShowNew(false)} className="text-ink-400 text-xs hover:text-ink-600">
            Cancel
          </button>
        </form>
      ) : (
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          type="button"
          onClick={() => setShowNew(true)}
          className="rounded-lg border border-dashed border-mist-300 px-3.5 py-1.5 text-xs text-ink-500 hover:border-accent/40 hover:text-accent transition-all"
        >
          + Project
        </motion.button>
      )}
    </div>
  );
}
