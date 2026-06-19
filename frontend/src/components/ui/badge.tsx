import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type BadgeVariant =
  | "default"
  | "indigo"
  | "green"
  | "amber"
  | "red"
  | "zinc";

const styles: Record<BadgeVariant, string> = {
  default: "bg-zinc-800 text-zinc-300",
  indigo: "bg-indigo-500/15 text-indigo-300 border border-indigo-500/20",
  green: "bg-green-500/15 text-green-300 border border-green-500/20",
  amber: "bg-amber-500/15 text-amber-300 border border-amber-500/20",
  red: "bg-red-500/15 text-red-300 border border-red-500/20",
  zinc: "bg-zinc-800/60 text-zinc-400 border border-zinc-700/50",
};

/** Trace/run statüsünü renge eşler. */
export function statusVariant(status: string): BadgeVariant {
  switch (status) {
    case "completed":
    case "passed":
      return "green";
    case "running":
    case "pending":
      return "indigo";
    case "error":
    case "failed":
    case "timeout":
    case "max_steps_exceeded":
      return "red";
    case "interrupted":
      return "amber";
    case "skipped":
      return "zinc";
    default:
      return "zinc";
  }
}

export function Badge({
  variant = "default",
  children,
  className,
}: {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
