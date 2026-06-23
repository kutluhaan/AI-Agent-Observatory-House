"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, Zap, TestTube2, Users, ChevronRight } from "lucide-react";
import { useAuth } from "@/contexts/auth";
import { api, type OrgDashboard, type OrgLeaderboardEntry, type TeamLeaderboardEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtPct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}
function fmtUsd(v: number | null): string {
  if (v == null) return "—";
  return `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`;
}
function fmtDur(ms: number | null): string {
  if (ms == null) return "—";
  const s = ms / 1000;
  return s < 60 ? `${s.toFixed(1)}s` : `${(s / 60).toFixed(1)}dk`;
}
function rateColor(v: number | null): string {
  if (v == null) return "text-zinc-500";
  return v >= 0.99 ? "text-green-400" : v >= 0.6 ? "text-amber-400" : "text-red-400";
}

const QUICK_LINKS = [
  { icon: Zap, label: "Agents", description: "AI agent'ları kur ve çalıştır", href: "/agents" },
  { icon: Users, label: "Ekipler", description: "Çok-agent ekipleri", href: "/teams" },
  { icon: Activity, label: "Traces", description: "Çalıştırmaları izle", href: "/traces" },
  { icon: TestTube2, label: "Test Suites", description: "Otomatik test", href: "/test-suites" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<OrgDashboard | null>(null);

  useEffect(() => {
    if (user && !user.org_id) router.replace("/create-org");
  }, [user, router]);

  useEffect(() => {
    if (user?.org_id) api.get<OrgDashboard>("/dashboard").then(setStats).catch(() => {});
  }, [user?.org_id]);

  if (!user?.org_id) return null;
  const firstName = user.full_name?.split(" ")[0] ?? "there";
  const hasData = stats && (stats.counts.total_runs > 0 || (stats.counts.teams ?? 0) > 0);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-12">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-zinc-100">Merhaba, {firstName}</h1>
        <p className="mt-1.5 text-sm text-zinc-500">{user.org_name ?? user.org_slug} workspace</p>
      </div>

      <div className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {QUICK_LINKS.map(({ icon: Icon, label, description, href }) => (
          <Link
            key={label}
            href={href}
            className="group flex h-full flex-col gap-2 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900/70"
          >
            <Icon size={18} className="text-indigo-400" />
            <div>
              <p className="text-sm font-medium text-zinc-200">{label}</p>
              <p className="text-xs text-zinc-500">{description}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* #7 — bir org, agent'ları ve ekipleri kadar iyidir → agent+ekip odaklı */}
      {hasData ? (
        <>
          {/* Kompakt org şeridi */}
          <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-zinc-800/60 bg-zinc-900/30 px-4 py-3">
            <StatChip label="Agent" value={String(stats!.counts.agents)} />
            <StatChip label="Ekip" value={String(stats!.counts.teams ?? 0)} />
            <StatChip label="Test run" value={String(stats!.counts.total_runs)} />
            <StatChip label="Başarılı run" value={fmtPct(stats!.success_run_rate)} accent />
            <StatChip label="Judge" value={stats!.avg_judge_score != null ? stats!.avg_judge_score.toFixed(2) : "—"} />
            <StatChip label="Ort. maliyet" value={fmtUsd(stats!.avg_cost_usd)} />
          </div>

          {/* İki lider tablosu yan yana */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <section>
              <h3 className="mb-2 text-[11px] uppercase tracking-wide text-zinc-500">
                Agent sıralaması · {stats!.agents_evaluated} değerlendirildi
              </h3>
              {stats!.leaderboard.length === 0 ? (
                <EmptyBox text="Henüz agent test verisi yok." />
              ) : (
                <div className="overflow-hidden rounded-xl border border-zinc-800/80">
                  {stats!.leaderboard.slice(0, 8).map((a, i) => (
                    <AgentRow key={a.agent_id} entry={a} rank={i + 1} first={i === 0} />
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-[11px] uppercase tracking-wide text-zinc-500">
                Ekip sıralaması · {stats!.teams_evaluated} değerlendirildi
              </h3>
              {stats!.team_leaderboard.length === 0 ? (
                <EmptyBox text="Henüz ekip yok." />
              ) : (
                <div className="overflow-hidden rounded-xl border border-zinc-800/80">
                  {stats!.team_leaderboard.slice(0, 8).map((t, i) => (
                    <TeamRow key={t.team_id} entry={t} rank={i + 1} first={i === 0} />
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      ) : (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">
          Henüz veri yok. Agent/ekip çalıştırınca performansları burada toplanır.
        </p>
      )}
    </div>
  );
}

function StatChip({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className={cn("text-sm font-semibold", accent ? "text-green-400" : "text-zinc-100")}>{value}</span>
      <span className="text-[11px] text-zinc-600">{label}</span>
    </div>
  );
}

function EmptyBox({ text }: { text: string }) {
  return (
    <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">{text}</p>
  );
}

function AgentRow({ entry, rank, first }: { entry: OrgLeaderboardEntry; rank: number; first: boolean }) {
  return (
    <Link
      href={`/agents/${entry.agent_id}/performance`}
      className={cn("flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-zinc-900/60", !first && "border-t border-zinc-800/60")}
    >
      <span className="w-4 text-center text-xs font-semibold text-zinc-600">{rank}</span>
      <span className="flex-1 truncate text-sm text-zinc-200">{entry.name}</span>
      <span className="text-[11px] text-zinc-600">{entry.total_cases} case</span>
      <span className={cn("w-11 text-right text-sm font-semibold", rateColor(entry.pass_rate))}>{fmtPct(entry.pass_rate)}</span>
      <ChevronRight size={14} className="text-zinc-700" />
    </Link>
  );
}

function TeamRow({ entry, rank, first }: { entry: TeamLeaderboardEntry; rank: number; first: boolean }) {
  return (
    <Link
      href={`/teams/${entry.team_id}`}
      className={cn("flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-zinc-900/60", !first && "border-t border-zinc-800/60")}
    >
      <span className="w-4 text-center text-xs font-semibold text-zinc-600">{rank}</span>
      <span className="flex-1 truncate text-sm text-zinc-200">{entry.name}</span>
      <span className="text-[11px] text-zinc-600">{entry.members} üye · {entry.total_runs} run</span>
      <span className="w-10 text-right text-[11px] text-zinc-500">{fmtDur(entry.avg_duration_ms)}</span>
      <span className={cn("w-11 text-right text-sm font-semibold", rateColor(entry.success_rate))}>{fmtPct(entry.success_rate)}</span>
      <ChevronRight size={14} className="text-zinc-700" />
    </Link>
  );
}
