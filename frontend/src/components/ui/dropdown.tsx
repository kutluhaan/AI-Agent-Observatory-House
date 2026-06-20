"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DropdownOption {
  value: string;
  label: string;
  hint?: string;
}

export function Dropdown({
  label,
  value,
  options,
  onChange,
  placeholder = "Select…",
  className,
}: {
  label?: string;
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = options.find((o) => o.value === value);

  return (
    <div className={cn("flex flex-col gap-1.5", className)} ref={ref}>
      {label && (
        <span className="text-xs font-medium tracking-wide text-zinc-400">{label}</span>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className={cn(
            "flex h-9 w-full items-center justify-between rounded-lg border bg-zinc-900/60 px-3 text-sm",
            "transition-colors duration-150 focus:outline-none focus:ring-1",
            open
              ? "border-indigo-500 ring-1 ring-indigo-500/20"
              : "border-zinc-800 hover:border-zinc-700",
          )}
        >
          <span className={selected ? "text-zinc-100" : "text-zinc-600"}>
            {selected ? selected.label : placeholder}
          </span>
          <ChevronDown
            size={14}
            className={cn("shrink-0 text-zinc-500 transition-transform", open && "rotate-180")}
          />
        </button>

        {open && (
          <div className="absolute z-20 mt-1.5 max-h-64 w-full overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-1 shadow-xl animate-slide-up">
            {options.map((opt) => {
              const isSel = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                    isSel ? "bg-indigo-500/10 text-indigo-200" : "text-zinc-300 hover:bg-zinc-900",
                  )}
                >
                  <Check
                    size={14}
                    className={cn("mt-0.5 shrink-0", isSel ? "text-indigo-400" : "text-transparent")}
                  />
                  <span className="flex-1">
                    <span className="block">{opt.label}</span>
                    {opt.hint && <span className="block text-xs text-zinc-600">{opt.hint}</span>}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
