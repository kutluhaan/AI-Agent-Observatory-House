"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, Zap, TestTube2, ChevronRight } from "lucide-react";
import { useAuth } from "@/contexts/auth";
import { api, type OrgDashboard, type OrgLeaderboardEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtPct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}
function fmtUsd(v: number | null): string {
  if (v == null) return "—";
  return `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`;
}

const QUICK_LINKS = [
  {
    icon: Zap,
    label: "Agents",
    description: "Build and run AI agents",
    href: "/agents",
    enabled: true,
  },
  {
    icon: Activity,
    label: "Traces",
    description: "Observe agent execution",
    href: "/traces",
    enabled: true,
  },
  {
    icon: TestTube2,
    label: "Test Suites",
    description: "Automated agent testing",
    href: "/test-suites",
    enabled: true,
  },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<OrgDashboard | null>(null);

  useEffect(() => {
    if (user && !user.org_id) {
      router.replace("/create-org");
    }
  }, [user, router]);

  useEffect(() => {
    if (user?.org_id) {
      api.get<OrgDashboard>("/dashboard").then(setStats).catch(() => {});
    }
  }, [user?.org_id]);

  if (!user?.org_id) return null;

  const firstName = user.full_name?.split(" ")[0] ?? "there";

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-12">
      <div className="mb-10">
        <h1 className="text-2xl font-semibold text-zinc-100">
          Good morning, {firstName}
        </h1>
        <p className="mt-1.5 text-sm text-zinc-500">
          {user.org_name ?? user.org_slug} workspace
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {QUICK_LINKS.map(({ icon: Icon, label, description, href, enabled }) => {
          const card = (
            <div
              className={
                "group relative flex h-full flex-col gap-2 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5 transition-colors " +
                (enabled ? "hover:border-zinc-700 hover:bg-zinc-900/70" : "opacity-50")
              }
            >
              <Icon size={18} className="text-indigo-400" />
              <div>
                <p className="text-sm font-medium text-zinc-200">{label}</p>
                <p className="text-xs text-zinc-500">{description}</p>
              </div>
              {!enabled && (
                <span className="absolute right-3 top-3 rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500">
                  soon
                </span>
              )}
            </div>
          );
          return enabled ? (
            <Link key={label} href={href}>
              {card}
            </Link>
          ) : (
            <div key={label}>{card}</div>
          );
        })}
      </div>

      {/* F5.2 — Org performans özeti (canlı; test verisi oluştukça dolar) */}
      {stats && stats.counts.total_runs > 0 && (
        <div className="mt-10">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            Org performansı
          </h2>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Başarılı run" value={fmtPct(stats.success_run_rate)} hint="tüm case'leri geçen" accent />
            <Kpi label="Ort. geçme oranı" value={fmtPct(stats.avg_pass_rate)} hint="case düzeyi" />
            <Kpi label="Judge skoru" value={stats.avg_judge_score != null ? stats.avg_judge_score.toFixed(2) : "—"} />
            <Kpi label="Ort. maliyet" value={fmtUsd(stats.avg_cost_usd)} hint="run başına" />
          </div>

          {stats.leaderboard.length > 0 && (
            <>
              <h3 className="mb-2 text-[11px] uppercase tracking-wide text-zinc-600">
                Agent sıralaması · {stats.agents_evaluated} değerlendirildi
              </h3>
              <div className="overflow-hidden rounded-xl border border-zinc-800/80">
                {stats.leaderboard.slice(0, 8).map((a, i) => (
                  <LeaderRow key={a.agent_id} entry={a} rank={i + 1} first={i === 0} />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function LeaderRow({ entry, rank, first }: { entry: OrgLeaderboardEntry; rank: number; first: boolean }) {
  return (
    <Link
      href={`/agents/${entry.agent_id}/performance`}
      className={cn(
        "flex items-center gap-4 px-4 py-3 transition-colors hover:bg-zinc-900/60",
        !first && "border-t border-zinc-800/60",
      )}
    >
      <span className="w-5 text-center text-xs font-semibold text-zinc-600">{rank}</span>
      <span className="flex-1 truncate text-sm text-zinc-200">{entry.name}</span>
      <span className="text-xs text-zinc-500">{entry.total_cases} case</span>
      <span className="w-16 text-right text-xs text-zinc-400">
        {entry.avg_judge_score != null ? `J ${entry.avg_judge_score.toFixed(2)}` : "—"}
      </span>
      <span
        className={cn(
          "w-12 text-right text-sm font-semibold",
          entry.pass_rate != null && entry.pass_rate >= 0.99
            ? "text-green-400"
            : entry.pass_rate != null && entry.pass_rate >= 0.6
              ? "text-amber-400"
              : "text-red-400",
        )}
      >
        {fmtPct(entry.pass_rate)}
      </span>
      <ChevronRight size={14} className="text-zinc-700" />
    </Link>
  );
}

function Kpi({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
      <p className="text-[10px] uppercase tracking-wide text-zinc-600">{label}</p>
      <p className={cn("mt-0.5 text-lg font-semibold", accent ? "text-green-400" : "text-zinc-100")}>{value}</p>
      {hint && <p className="text-[10px] text-zinc-700">{hint}</p>}
    </div>
  );
}
