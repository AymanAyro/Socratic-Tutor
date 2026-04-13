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

const LS_CONCEPT = "st_concept_id";

const loadStoredMessages = (): ChatMessage[] => {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem("st_messages");
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChatMessage[]) : [];
  } catch {
    return [];
  }
};

/** Clears Stage 2 / mode hints stored for Tutor reload (session id is cleared separately). */
export function clearSessionPersistMeta() {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem("st_use_stage2");
  localStorage.removeItem("st_session_mode");
  localStorage.removeItem("st_teaching_phase");
}

export const useSessionStore = create<State>((set, get) => ({
  userId: typeof localStorage !== "undefined" ? localStorage.getItem("st_user_id") : null,
  projectId: typeof localStorage !== "undefined" ? localStorage.getItem("st_project_id") : null,
  documentId: null,
  conceptId: typeof localStorage !== "undefined" ? localStorage.getItem(LS_CONCEPT) : null,
  sessionId: typeof localStorage !== "undefined" ? localStorage.getItem("st_session_id") : null,
  sessionName: typeof localStorage !== "undefined" ? localStorage.getItem("st_session_name") : null,
  messages: loadStoredMessages(),
  setUserId: (id) => {
    localStorage.setItem("st_user_id", id);
    set({ userId: id });
  },
  setProjectId: (id) => {
    if (id) localStorage.setItem("st_project_id", id);
    else localStorage.removeItem("st_project_id");
    if (typeof localStorage !== "undefined") localStorage.removeItem(LS_CONCEPT);
    set({ projectId: id, documentId: null, conceptId: null });
  },
  setDocumentId: (id) => set({ documentId: id }),
  setConceptId: (id) => {
    if (typeof localStorage !== "undefined") {
      if (id) localStorage.setItem(LS_CONCEPT, id);
      else localStorage.removeItem(LS_CONCEPT);
    }
    set({ conceptId: id });
  },
  setSessionId: (id) => {
    if (id) localStorage.setItem("st_session_id", id);
    else localStorage.removeItem("st_session_id");
    set({ sessionId: id });
  },
  setSessionName: (name) => {
    if (name) localStorage.setItem("st_session_name", name);
    else localStorage.removeItem("st_session_name");
    set({ sessionName: name });
  },
  appendMessage: (m) =>
    set((state) => {
      const messages: ChatMessage[] = [...state.messages, { ...m, id: uid() }];
      localStorage.setItem("st_messages", JSON.stringify(messages));
      return { messages };
    }),
  appendTutorChunk: (chunk) => {
    const msgs = get().messages;
    const last = msgs[msgs.length - 1];
    if (last?.role === "tutor") {
      const messages: ChatMessage[] = [
        ...msgs.slice(0, -1),
        { ...last, text: `${last.text}${chunk}` },
      ];
      localStorage.setItem("st_messages", JSON.stringify(messages));
      set({ messages });
    } else {
      const messages: ChatMessage[] = [...msgs, { id: uid(), role: "tutor", text: chunk }];
      localStorage.setItem("st_messages", JSON.stringify(messages));
      set({ messages });
    }
  },
  resetChat: () => {
    localStorage.removeItem("st_messages");
    localStorage.removeItem("st_session_id");
    localStorage.removeItem("st_session_name");
    clearSessionPersistMeta();
    set({ messages: [], sessionId: null, sessionName: null });
  },
}));
