import { motion } from "framer-motion";

type Props = { role: "student" | "tutor"; text: string };

export default function ChatBubble({ role, text }: Props) {
  const isTutor = role === "tutor";
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`flex ${isTutor ? "justify-start" : "justify-end"}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isTutor
            ? "bg-white border border-mist-200 text-ink-800 shadow-sm border-l-[3px] border-l-accent/60"
            : "bg-gradient-to-br from-accent to-accent-dim text-white shadow-md shadow-accent/20"
        }`}
      >
        <div
          className={`text-[10px] uppercase tracking-wider mb-1 ${
            isTutor ? "text-accent font-semibold" : "text-white/70"
          }`}
        >
          {isTutor ? "Tutor" : "You"}
        </div>
        <div className="whitespace-pre-wrap">{text}</div>
      </div>
    </motion.div>
  );
}
