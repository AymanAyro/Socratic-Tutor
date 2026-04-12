import { motion } from "framer-motion";
import { useState } from "react";

type Props = {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

export default function InputBar({ onSend, disabled, placeholder }: Props) {
  const [value, setValue] = useState("");
  const canSend = !disabled && value.trim().length > 0;

  const submit = () => {
    const t = value.trim();
    if (t) {
      onSend(t);
      setValue("");
    }
  };

  return (
    <div className="flex gap-2 items-end border-t border-mist-200/60 pt-4">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder ?? "Your answer..."}
        rows={2}
        className="flex-1 resize-none rounded-xl border border-mist-200 bg-white/80 px-4 py-2.5 text-sm outline-none transition-all duration-200 focus:border-accent/50 focus:ring-2 focus:ring-accent/20 focus:shadow-sm focus:shadow-accent/10 disabled:opacity-50"
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
        className="rounded-xl bg-gradient-to-r from-accent to-accent-dim text-white px-5 py-2.5 text-sm font-medium shadow-sm shadow-accent/20 transition-opacity disabled:opacity-40 disabled:shadow-none"
      >
        Send
      </motion.button>
    </div>
  );
}
