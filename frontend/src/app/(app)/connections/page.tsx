"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Link2, Mail, Database, Wrench, Github, Bell } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";
import { GoogleSection } from "@/components/connections/google-section";
import DbConnectionsPage from "@/app/(app)/db-connections/page";
import McpServersPage from "@/app/(app)/mcp-servers/page";
import CustomToolsPage from "@/app/(app)/custom-tools/page";
import GithubConnectionsPage from "@/app/(app)/github-connections/page";
import NotificationChannelsPage from "@/app/(app)/notification-channels/page";

type CatKey = "google" | "database" | "tools" | "github" | "notify";

const CATS: { key: CatKey; label: string; icon: typeof Mail; desc: string }[] = [
  { key: "google", label: "Google", icon: Mail, desc: "Gmail · Takvim · Drive hesabını bağla (OAuth). Agent senin adına okur/yazar." },
  { key: "database", label: "Veritabanı", icon: Database, desc: "PostgreSQL bağlantısı (şifreli DSN). Agent SALT-OKUNUR sorgu çalıştırır." },
  { key: "tools", label: "Araç Bağlantıları", icon: Wrench, desc: "Dış araçlar: MCP sunucuları + kendi özel HTTP endpoint'lerin." },
  { key: "github", label: "GitHub", icon: Github, desc: "GitHub PAT (şifreli). Repo/issue/kod arama + dosya okuma." },
  { key: "notify", label: "Bildirimler", icon: Bell, desc: "Webhook kanalı (Slack/Discord/Teams). Agent mesaj/uyarı gönderir." },
];

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-20"><Spinner className="h-5 w-5" /></div>}>
      <ConnectionsHub />
    </Suspense>
  );
}

function ConnectionsHub() {
  const params = useSearchParams();
  // OAuth callback → google sekmesi; ?tab= varsa onu aç
  const initial = (params.get("google") ? "google" : (params.get("tab") as CatKey)) || "google";
  const [tab, setTab] = useState<CatKey>(CATS.some((c) => c.key === initial) ? initial : "google");

  const active = CATS.find((c) => c.key === tab)!;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-center gap-2">
        <Link2 size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Bağlantılar</h1>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        {/* Kategori navigasyonu */}
        <aside className="md:w-64 md:shrink-0">
          <div className="flex flex-col gap-1">
            {CATS.map((c) => {
              const Icon = c.icon;
              const on = c.key === tab;
              return (
                <button
                  key={c.key}
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
            })}
          </div>
        </aside>

        {/* İçerik */}
        <section className="min-w-0 flex-1">
          <div className="mb-4 rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-4 py-3">
            <p className="text-sm font-medium text-zinc-200">{active.label}</p>
            <p className="mt-0.5 text-xs text-zinc-500">{active.desc}</p>
          </div>

          {tab === "google" && <div className="px-1"><GoogleSection /></div>}
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

/** Gömülü eski sayfa bileşenleri kendi mx-auto/padding'ini taşır; negatif margin'le sıkıştırma yok, olduğu gibi gösterilir. */
function Embed({ children }: { children: React.ReactNode }) {
  return <div className="[&_h1]:text-base">{children}</div>;
}
