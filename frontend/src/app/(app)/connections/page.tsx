"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Link2, Database, Wrench, Bell } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";
import { GoogleServiceSection } from "@/components/connections/google-service-section";
import DbConnectionsPage from "@/app/(app)/db-connections/page";
import McpServersPage from "@/app/(app)/mcp-servers/page";
import CustomToolsPage from "@/app/(app)/custom-tools/page";
import GithubConnectionsPage from "@/app/(app)/github-connections/page";
import NotificationChannelsPage from "@/app/(app)/notification-channels/page";

// Source: Simple Icons (simpleicons.org)
function GmailIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
    </svg>
  );
}

function GoogleDriveIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12.01 1.485c-2.082 0-3.754.02-3.743.047.01.02 1.708 3.001 3.774 6.62l3.76 6.574h3.76c2.081 0 3.753-.02 3.742-.047-.005-.02-1.708-3.001-3.775-6.62l-3.76-6.574zm-4.76 1.73a789.828 789.861 0 0 0-3.63 6.319L0 15.868l1.89 3.298 1.885 3.297 3.62-6.335 3.618-6.33-1.88-3.287C8.1 4.704 7.255 3.22 7.25 3.214zm2.259 12.653-.203.348c-.114.198-.96 1.672-1.88 3.287a423.93 423.948 0 0 1-1.698 2.97c-.01.026 3.24.042 7.222.042h7.244l1.796-3.157c.992-1.734 1.85-3.23 1.906-3.323l.104-.167h-7.249z"/>
    </svg>
  );
}

function GoogleCalendarIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M18.316 5.684H24v12.632h-5.684V5.684zM5.684 24h12.632v-5.684H5.684V24zM18.316 5.684V0H1.895A1.894 1.894 0 0 0 0 1.895v16.421h5.684V5.684h12.632zm-7.207 6.25v-.065c.272-.144.5-.349.687-.617s.279-.595.279-.982c0-.379-.099-.72-.3-1.025a2.05 2.05 0 0 0-.832-.714 2.703 2.703 0 0 0-1.197-.257c-.6 0-1.094.156-1.481.467-.386.311-.65.671-.793 1.078l1.085.452c.086-.249.224-.461.413-.633.189-.172.445-.257.767-.257.33 0 .602.088.816.264a.86.86 0 0 1 .322.703c0 .33-.12.589-.36.778-.24.19-.535.284-.886.284h-.567v1.085h.633c.407 0 .748.109 1.02.327.272.218.407.499.407.843 0 .336-.129.614-.387.832s-.565.327-.924.327c-.351 0-.651-.103-.897-.311-.248-.208-.422-.502-.521-.881l-1.096.452c.178.616.505 1.082.977 1.401.472.319.984.478 1.538.477a2.84 2.84 0 0 0 1.293-.291c.382-.193.684-.458.902-.794.218-.336.327-.72.327-1.149 0-.429-.115-.797-.344-1.105a2.067 2.067 0 0 0-.881-.689zm2.093-1.931.602.913L15 10.045v5.744h1.187V8.446h-.827l-2.158 1.557zM22.105 0h-3.289v5.184H24V1.895A1.894 1.894 0 0 0 22.105 0zm-3.289 23.5 4.684-4.684h-4.684V23.5zM0 22.105C0 23.152.848 24 1.895 24h3.289v-5.184H0v3.289z"/>
    </svg>
  );
}

function GitHubIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
    </svg>
  );
}

type CatKey = "gmail" | "gcalendar" | "gdrive" | "database" | "tools" | "github" | "notify";
type IconComp = React.ComponentType<{ size?: number; className?: string }>;

const CATS: { key: CatKey; label: string; icon: IconComp; desc: string }[] = [
  { key: "gmail", label: "Gmail", icon: GmailIcon, desc: "E-posta oku, ara ve gönder. Agent senin adına çalışır." },
  { key: "gcalendar", label: "Google Takvim", icon: GoogleCalendarIcon, desc: "Etkinlik listele ve oluştur." },
  { key: "gdrive", label: "Google Drive", icon: GoogleDriveIcon, desc: "Dosya ara ve içeriklerini oku." },
  { key: "database", label: "Veritabanı", icon: Database, desc: "PostgreSQL bağlantısı (şifreli DSN). Agent SALT-OKUNUR sorgu çalıştırır." },
  { key: "tools", label: "Araç Bağlantıları", icon: Wrench, desc: "Dış araçlar: MCP sunucuları + kendi özel HTTP endpoint'lerin." },
  { key: "github", label: "GitHub", icon: GitHubIcon, desc: "GitHub PAT (şifreli). Repo/issue/kod arama + dosya okuma." },
  { key: "notify", label: "Bildirimler", icon: Bell, desc: "Webhook kanalı (Slack/Discord/Teams). Agent mesaj/uyarı gönderir." },
];

const GOOGLE_KEYS: CatKey[] = ["gmail", "gcalendar", "gdrive"];

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-20"><Spinner className="h-5 w-5" /></div>}>
      <ConnectionsHub />
    </Suspense>
  );
}

function ConnectionsHub() {
  const params = useSearchParams();
  const initial = (params.get("google") ? "gmail" : (params.get("tab") as CatKey)) || "gmail";
  const [tab, setTab] = useState<CatKey>(CATS.some((c) => c.key === initial) ? initial : "gmail");

  const active = CATS.find((c) => c.key === tab)!;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-center gap-2">
        <Link2 size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Bağlantılar</h1>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        <aside className="md:w-64 md:shrink-0">
          <div className="flex flex-col gap-1">
            <p className="mb-0.5 px-1 text-[10px] font-medium uppercase tracking-wider text-zinc-600">Google</p>
            {CATS.filter((c) => GOOGLE_KEYS.includes(c.key)).map((c) => <NavItem key={c.key} c={c} tab={tab} setTab={setTab} />)}
            <div className="my-1 border-t border-zinc-800/60" />
            {CATS.filter((c) => !GOOGLE_KEYS.includes(c.key)).map((c) => <NavItem key={c.key} c={c} tab={tab} setTab={setTab} />)}
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          <div className="mb-4 rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-4 py-3">
            <p className="text-sm font-medium text-zinc-200">{active.label}</p>
            <p className="mt-0.5 text-xs text-zinc-500">{active.desc}</p>
          </div>

          {tab === "gmail" && <GoogleServiceSection service="gmail" />}
          {tab === "gcalendar" && <GoogleServiceSection service="gcalendar" />}
          {tab === "gdrive" && <GoogleServiceSection service="gdrive" />}
          {tab === "database" && <Embed><DbConnectionsPage /></Embed>}
          {tab === "github" && <Embed><GithubConnectionsPage /></Embed>}
          {tab === "notify" && <Embed><NotificationChannelsPage /></Embed>}
          {tab === "tools" && (
            <Embed>
              <McpServersPage />
              <div className="mx-auto my-2 max-w-3xl border-t border-zinc-800/60" />
              <CustomToolsPage />
            </Embed>
          )}
        </section>
      </div>
    </div>
  );
}

function NavItem({ c, tab, setTab }: { c: (typeof CATS)[number]; tab: CatKey; setTab: (k: CatKey) => void }) {
  const Icon = c.icon;
  const on = c.key === tab;
  return (
    <button
      onClick={() => setTab(c.key)}
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors",
        on ? "border-indigo-500/40 bg-indigo-500/10" : "border-zinc-800/70 hover:border-zinc-700 hover:bg-zinc-900/40",
      )}
    >
      <Icon size={15} className={cn("mt-0.5 shrink-0", on ? "text-indigo-300" : "text-zinc-500")} />
      <span className="min-w-0">
        <span className={cn("block text-sm font-medium", on ? "text-zinc-100" : "text-zinc-300")}>{c.label}</span>
        <span className="block text-[11px] leading-snug text-zinc-600">{c.desc}</span>
      </span>
    </button>
  );
}

function Embed({ children }: { children: React.ReactNode }) {
  return <div className="[&_h1]:text-base">{children}</div>;
}
