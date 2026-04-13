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
        className={`max-w-[85%] px-4 py-3 text-sm leading-relaxed ${
          isTutor
            ? "rounded-[18px] rounded-bl-[4px] bg-white border border-[#e8e8f0] text-[#1a1a2e] shadow-sm"
            : "rounded-[18px] rounded-br-[4px] bg-[#6C63FF] text-white shadow-md border border-[#6C63FF]"
        }`}
      >
        <div
          className={`text-[10px] uppercase tracking-wider mb-1 ${
            isTutor ? "text-accent font-semibold" : "text-white/80"
          }`}
        >
          {isTutor ? "Tutor" : "You"}
        </div>
        <div className="whitespace-pre-wrap">{text}</div>
      </div>
    </motion.div>
  );
}
