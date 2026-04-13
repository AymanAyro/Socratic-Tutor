import { create } from "zustand";

type Role = "student" | "tutor";

export type ChatMessage = { id: string; role: Role; text: string };

type State = {
  userId: string | null;
  projectId: string | null;
  documentId: string | null;
  conceptId: string | null;
  sessionId: string | null;
  sessionName: string | null;
  messages: ChatMessage[];
  setUserId: (id: string) => void;
  setProjectId: (id: string | null) => void;
  setDocumentId: (id: string | null) => void;
  setConceptId: (id: string | null) => void;
  setSessionId: (id: string | null) => void;
  setSessionName: (name: string | null) => void;
  appendMessage: (m: Omit<ChatMessage, "id">) => void;
  appendTutorChunk: (chunk: string) => void;
  resetChat: () => void;
};

const uid = () => crypto.randomUUID();

export const useSessionStore = create<State>((set, get) => ({
  userId: typeof localStorage !== "undefined" ? localStorage.getItem("st_user_id") : null,
  projectId: typeof localStorage !== "undefined" ? localStorage.getItem("st_project_id") : null,
  documentId: null,
  conceptId: null,
  sessionId: null,
  sessionName: null,
  messages: [],
  setUserId: (id) => {
    localStorage.setItem("st_user_id", id);
    set({ userId: id });
  },
  setProjectId: (id) => {
    if (id) localStorage.setItem("st_project_id", id);
    else localStorage.removeItem("st_project_id");
    set({ projectId: id, documentId: null, conceptId: null });
  },
  setDocumentId: (id) => set({ documentId: id }),
  setConceptId: (id) => set({ conceptId: id }),
  setSessionId: (id) => set({ sessionId: id }),
  setSessionName: (name) => set({ sessionName: name }),
  appendMessage: (m) =>
    set({ messages: [...get().messages, { ...m, id: uid() }] }),
  appendTutorChunk: (chunk) => {
    const msgs = get().messages;
    const last = msgs[msgs.length - 1];
    if (last?.role === "tutor") {
      set({
        messages: [
          ...msgs.slice(0, -1),
          { ...last, text: last.text + chunk },
        ],
      });
    } else {
      set({ messages: [...msgs, { id: uid(), role: "tutor", text: chunk }] });
    }
  },
  resetChat: () => set({ messages: [], sessionId: null, sessionName: null }),
}));
