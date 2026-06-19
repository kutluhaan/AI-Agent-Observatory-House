import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";

interface AlertProps {
  variant?: "error" | "success" | "info";
  children: ReactNode;
  className?: string;
}

const config = {
  error: {
    container: "bg-red-500/10 border-red-500/20 text-red-300",
    icon: AlertCircle,
    iconClass: "text-red-400 shrink-0 mt-0.5",
  },
  success: {
    container: "bg-green-500/10 border-green-500/20 text-green-300",
    icon: CheckCircle2,
    iconClass: "text-green-400 shrink-0 mt-0.5",
  },
  info: {
    container: "bg-indigo-500/10 border-indigo-500/20 text-indigo-300",
    icon: Info,
    iconClass: "text-indigo-400 shrink-0 mt-0.5",
  },
};

export function Alert({ variant = "info", children, className }: AlertProps) {
  const { container, icon: Icon, iconClass } = config[variant];
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm",
        container,
        className,
      )}
    >
      <Icon size={15} className={iconClass} />
      <span className="leading-relaxed">{children}</span>
    </div>
  );
}
