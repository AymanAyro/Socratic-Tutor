import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

type Props = {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

export default function InputBar({ onSend, disabled, placeholder }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const canSend = !disabled && value.trim().length > 0;

  const submit = () => {
    const t = value.trim();
    if (t) {
      onSend(t);
      setValue("");
    }
  };

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  return (
    <div className="border-t border-border pt-4">
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder ?? "Your answer..."}
          rows={1}
          aria-label="Your answer"
          className="flex-1 resize-none rounded-xl border border-border bg-surface-2 text-text px-4 py-2.5 text-sm outline-none transition-all duration-200 focus:border-accent/60 focus:ring-2 focus:ring-accent/20 disabled:opacity-50"
          disabled={disabled}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) submit();
            }
          }}
        />
        <motion.button
          whileHover={canSend ? { scale: 1.04 } : {}}
          whileTap={canSend ? { scale: 0.96 } : {}}
          onClick={submit}
          disabled={!canSend}
          aria-label={disabled ? "Waiting for tutor response" : "Send answer"}
          className="rounded-xl bg-gradient-to-r from-accent to-accent-dim text-white px-5 py-2.5 text-sm font-medium shadow-sm shadow-accent/20 transition-opacity disabled:opacity-40 disabled:shadow-none"
        >
          {disabled ? "..." : "Send"}
        </motion.button>
      </div>
      <p className="text-xs text-muted mt-1">Enter to send · Shift+Enter for new line</p>
    </div>
  );
}
