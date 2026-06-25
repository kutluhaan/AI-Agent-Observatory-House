import {
  Compass,
  ClipboardList,
  Microscope,
  Wrench,
  CheckCircle2,
  UserCog,
  type LucideIcon,
} from "lucide-react";

// F8/A1 — her ekip rolüne uygun ikon + renk (UI'da tutarlı kullanılır)
const ROLE_ICONS: Record<string, LucideIcon> = {
  coordinator: Compass,
  planner: ClipboardList,
  researcher: Microscope,
  worker: Wrench,
  evaluator: CheckCircle2,
};

const ROLE_COLORS: Record<string, string> = {
  coordinator: "text-amber-400",
  planner: "text-sky-400",
  researcher: "text-violet-400",
  worker: "text-emerald-400",
  evaluator: "text-rose-400",
};

export function roleIcon(role: string): LucideIcon {
  return ROLE_ICONS[role] ?? UserCog; // bilinmeyen/özel rol → genel ikon
}

export function roleColor(role: string): string {
  return ROLE_COLORS[role] ?? "text-zinc-400";
}
