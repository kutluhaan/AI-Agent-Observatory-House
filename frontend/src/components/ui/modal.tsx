"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Modal({
  open,
  onClose,
  title,
  children,
  className,
}: {
  open: boolean;
  onClose?: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!open || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={cn(
          "relative z-10 w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-950 shadow-xl",
          "animate-slide-up",
          className,
        )}
      >
        {(title || onClose) && (
          <div className="flex items-center justify-between border-b border-zinc-900 px-5 py-3.5">
            <h2 className="text-sm font-semibold text-zinc-100">{title}</h2>
            {onClose && (
              <button
                onClick={onClose}
                className="text-zinc-600 transition-colors hover:text-zinc-300"
              >
                <X size={16} />
              </button>
            )}
          </div>
        )}
        <div className="p-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
