import { motion } from "framer-motion";
import { useCallback, useState, type DragEvent } from "react";

type Props = {
  onFile: (file: File) => void;
  busy?: boolean;
};

export default function FileDropzone({ onFile, busy }: Props) {
  const [drag, setDrag] = useState(false);
  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDrag(false);
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    },
    [onFile]
  );

  return (
    <motion.div
      whileHover={{ scale: 1.005 }}
      onDragOver={(e: React.DragEvent) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className={`relative rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all duration-300 overflow-hidden ${
        drag
          ? "border-accent bg-accent-50 shadow-lg shadow-accent/10"
          : "border-mist-300 bg-white/60 hover:border-accent/40 hover:bg-white"
      }`}
    >
      {drag && (
        <div className="absolute inset-0 bg-gradient-to-r from-accent/5 via-accent/10 to-accent/5 animate-shimmer" />
      )}
      <div className="relative z-10">
        <div className="mx-auto w-12 h-12 rounded-xl bg-accent-50 flex items-center justify-center mb-3">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
          </svg>
        </div>
        <p className="text-ink-800 font-medium">Drop PDF, Markdown, or text</p>
        <p className="text-sm text-ink-500 mt-1">or choose a file</p>
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          disabled={busy}
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".pdf,.md,.txt,.markdown";
            input.onchange = () => {
              const f = input.files?.[0];
              if (f) onFile(f);
            };
            input.click();
          }}
          className="mt-4 rounded-lg border border-mist-200 bg-white px-5 py-2 text-sm font-medium text-ink-700 shadow-sm transition-all hover:shadow-md hover:border-accent/30 disabled:opacity-40"
        >
          Browse
        </motion.button>
      </div>
    </motion.div>
  );
}
