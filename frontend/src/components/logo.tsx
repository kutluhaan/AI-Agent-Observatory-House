import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  className?: string;
  showWordmark?: boolean;
  wordmarkSize?: "sm" | "md" | "lg";
}

const wordmarkSizes = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-lg",
};

export function Logo({
  size = 28,
  className,
  showWordmark = true,
  wordmarkSize = "md",
}: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      {/* Three concentric circles — zoom/observation metaphor */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        fill="none"
        aria-hidden
      >
        <circle
          cx="14"
          cy="14"
          r="12"
          stroke="#6366f1"
          strokeWidth="1.25"
          opacity="0.3"
        />
        <circle
          cx="14"
          cy="14"
          r="7.5"
          stroke="#6366f1"
          strokeWidth="1.25"
          opacity="0.6"
        />
        <circle cx="14" cy="14" r="3" fill="#6366f1" />
      </svg>

      {showWordmark && (
        <span
          className={cn(
            "font-semibold tracking-tight text-zinc-100",
            wordmarkSizes[wordmarkSize],
          )}
        >
          Observatory
        </span>
      )}
    </div>
  );
}
