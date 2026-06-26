import { cn } from "@/lib/utils";
import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  type TextareaHTMLAttributes,
} from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  /** İçeriğe göre yüksekliği otomatik büyüt (maxRows'a kadar, sonra scroll). */
  autoGrow?: boolean;
  /** autoGrow için maksimum görünür satır (varsayılan 8). */
  maxRows?: number;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, className, id, autoGrow, maxRows = 8, onChange, ...props }, ref) => {
    const taId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    const innerRef = useRef<HTMLTextAreaElement | null>(null);
    useImperativeHandle(ref, () => innerRef.current as HTMLTextAreaElement, []);

    const resize = useCallback(() => {
      const el = innerRef.current;
      if (!el || !autoGrow) return;
      el.style.height = "auto";
      const cs = window.getComputedStyle(el);
      const lh = parseFloat(cs.lineHeight) || 20;
      const extra =
        parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) +
        parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
      const max = lh * maxRows + extra;
      const next = Math.min(el.scrollHeight, max);
      el.style.height = `${next}px`;
      el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
    }, [autoGrow, maxRows]);

    // Kontrollü value değişince (programatik temizleme dahil) yeniden ölç
    useLayoutEffect(() => { resize(); }, [resize, props.value]);

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={taId} className="text-xs font-medium tracking-wide text-zinc-400">
            {label}
          </label>
        )}
        <textarea
          ref={innerRef}
          id={taId}
          onChange={(e) => { onChange?.(e); resize(); }}
          className={cn(
            "w-full rounded-lg border bg-zinc-900/60 px-3 py-2 text-sm text-zinc-100",
            "placeholder:text-zinc-600 transition-colors duration-150",
            "focus:outline-none focus:ring-1",
            error
              ? "border-red-500/50 focus:border-red-500 focus:ring-red-500/20"
              : "border-zinc-800 focus:border-indigo-500 focus:ring-indigo-500/20",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
          {...props}
        />
        {error && <p className="text-xs text-red-400">{error}</p>}
        {hint && !error && <p className="text-xs text-zinc-500">{hint}</p>}
      </div>
    );
  },
);

Textarea.displayName = "Textarea";
