import { motion, useAnimate, useReducedMotion } from "framer-motion";
import { useLayoutEffect } from "react";
import { cn } from "../../lib/utils";

/**
 * Aceternity-style “Text Generate Effect” adapted for chat:
 * @see https://ui.aceternity.com/components/text-generate-effect
 */
const PHRASE = "Tutor is thinking";

type Props = {
  className?: string;
};

export default function TypingIndicator({ className }: Props) {
  const [scope, animate] = useAnimate();
  const reduceMotion = useReducedMotion();

  useLayoutEffect(() => {
    if (reduceMotion) return;
    const id = requestAnimationFrame(() => {
      void animate(
        ".typing-indicator-word",
        { opacity: 1, filter: "blur(0px)" },
        { duration: 0.55, delay: (i) => i * 0.12 }
      );
    });
    return () => cancelAnimationFrame(id);
  }, [animate, reduceMotion]);

  const words = PHRASE.split(" ");

  return (
    <motion.div
      ref={scope}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex flex-wrap items-center gap-x-1.5 gap-y-0.5 px-3 py-2 rounded-xl border border-border/70 bg-surface-2/90 shadow-sm",
        className
      )}
    >
      <span className="sr-only">Tutor is typing</span>
      {words.map((word, idx) => (
        <span
          key={`${word}-${idx}`}
          className={cn(
            "typing-indicator-word text-sm font-medium text-muted",
            reduceMotion && "opacity-100"
          )}
          style={
            reduceMotion
              ? undefined
              : {
                  opacity: 0,
                  filter: "blur(8px)",
                }
          }
        >
          {word}
        </span>
      ))}
      <motion.span
        className="ml-0.5 inline-block h-3.5 w-px bg-accent align-middle rounded-full"
        animate={reduceMotion ? undefined : { opacity: [1, 0.25, 1] }}
        transition={{ duration: 0.85, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden
      />
    </motion.div>
  );
}
