"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Building2, Zap, Users, Search, ArrowLeft, Bot } from "lucide-react";
import { useAuth } from "@/contexts/auth";
import {
  api,
  type OrgDashboard,
  type OrgLeaderboardEntry,
  type TeamLeaderboardEntry,
  type SuiteTrendPoint,
  type DailyActivityPoint,
  type AgentUsagePoint,
  type LatencyBucket,
  type Agent,
  type Team,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Formatters ───────────────────────────────────────────────

function fmtPct(v: number | null) { return v == null ? "—" : `${Math.round(v * 100)}%`; }
function fmtUsd(v: number | null) { if (v == null) return "—"; return `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`; }
function fmtDur(ms: number | null) { if (ms == null) return "—"; const s = ms / 1000; return s < 60 ? `${s.toFixed(1)}s` : `${(s / 60).toFixed(1)}dk`; }
function rateColor(v: number | null) { if (v == null) return "text-zinc-500"; return v >= 0.99 ? "text-green-400" : v >= 0.6 ? "text-amber-400" : "text-red-400"; }
function barColor(v: number | null) { if (v == null) return "bg-zinc-600"; return v >= 0.99 ? "bg-green-500" : v >= 0.6 ? "bg-amber-500" : "bg-red-500"; }

type Scope = "org" | "agent" | "team";

// ── Page ─────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<OrgDashboard | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [scope, setScope] = useState<Scope>("org");
  const [agentId, setAgentId] = useState<string>("");
  const [teamId, setTeamId] = useState<string>("");
  const [q, setQ] = useState("");

  useEffect(() => { if (user && !user.org_id) router.replace("/create-org"); }, [user, router]);
  useEffect(() => {
    if (!user?.org_id) return;
    api.get<OrgDashboard>("/dashboard").then(setStats).catch(() => {});
    api.get<Agent[]>("/agents").then(setAgents).catch(() => {});
    api.get<Team[]>("/teams").then(setTeams).catch(() => {});
  }, [user?.org_id]);

  const agentKpi = useMemo(() => new Map(stats?.leaderboard.map((a) => [a.agent_id, a]) ?? []), [stats]);
  const teamKpi = useMemo(() => new Map(stats?.team_leaderboard.map((t) => [t.team_id, t]) ?? []), [stats]);

  function pickScope(s: Scope) { setScope(s); setQ(""); }

  if (!user?.org_id) return null;
  const firstName = user.full_name?.split(" ")[0] ?? "there";
  const hasData = stats && (stats.counts.total_runs > 0 || (stats.counts.teams ?? 0) > 0);

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-zinc-100">Merhaba, {firstName}</h1>
        <p className="mt-1.5 text-sm text-zinc-500">{user.org_name ?? user.org_slug} workspace</p>
      </div>

      {/* Org metrik şeridi */}
      {stats && (
        <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-zinc-800/60 bg-zinc-900/30 px-4 py-3">
          <StatChip label="Agent" value={String(stats.counts.agents)} />
          <StatChip label="Ekip" value={String(stats.counts.teams ?? 0)} />
          <StatChip label="Test run" value={String(stats.counts.total_runs)} />
          <StatChip label="Başarılı run" value={fmtPct(stats.success_run_rate)} accent />
          <StatChip label="Judge" value={stats.avg_judge_score != null ? stats.avg_judge_score.toFixed(2) : "—"} />
          <StatChip label="Ort. maliyet" value={fmtUsd(stats.avg_cost_usd)} />
        </div>
      )}

      {/* Scope seçici */}
      <div className="mb-6 flex items-center gap-1.5">
        <ScopeTab active={scope === "org"} onClick={() => pickScope("org")} icon={Building2} label="Organizasyon" />
        <ScopeTab active={scope === "agent"} onClick={() => pickScope("agent")} icon={Zap} label="Agent" />
        <ScopeTab active={scope === "team"} onClick={() => pickScope("team")} icon={Users} label="Ekip" />
      </div>

      {!hasData ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">
          Henüz veri yok. Agent/ekip çalıştırınca metrikler ve grafikler burada toplanır.
        </p>
      ) : scope === "org" ? (
        <OrgView stats={stats!} />
      ) : scope === "agent" ? (
        agentId ? (
          <SelectedHeader name={agents.find((a) => a.id === agentId)?.name ?? "Agent"} onBack={() => setAgentId("")}>
            <AgentView entry={agentKpi.get(agentId) ?? null} agentId={agentId} />
          </SelectedHeader>
        ) : (
          <PickGrid
            q={q} setQ={setQ} placeholder="Agent ara…"
            items={agents.map((a) => ({ id: a.id, name: a.name, sub: `${a.provider} · ${a.model}`, rate: agentKpi.get(a.id)?.pass_rate ?? null }))}
            onPick={setAgentId} icon={Bot}
          />
        )
      ) : (
        teamId ? (
          <SelectedHeader name={teams.find((t) => t.id === teamId)?.name ?? "Ekip"} onBack={() => setTeamId("")}>
            <TeamView entry={teamKpi.get(teamId) ?? null} teamId={teamId} />
          </SelectedHeader>
        ) : (
          <PickGrid
            q={q} setQ={setQ} placeholder="Ekip ara…"
            items={teams.map((t) => ({ id: t.id, name: t.name, sub: `${t.members.length} üye`, rate: teamKpi.get(t.id)?.success_rate ?? null }))}
            onPick={setTeamId} icon={Users}
          />
        )
      )}
    </div>
  );
}

// ── Org View ─────────────────────────────────────────────────

function OrgView({ stats }: { stats: OrgDashboard }) {
  const topAgents = stats.leaderboard.slice(0, 6);
  const topTeams = stats.team_leaderboard.slice(0, 6);
  const hasTrend = stats.trend.length >= 2;
  const hasActivity = stats.daily_activity?.some((d) => d.total > 0) ?? false;
  const hasUsage = (stats.agent_usage?.length ?? 0) > 0;
  const hasLatency = stats.latency_dist?.some((d) => d.count > 0) ?? false;
  const hasCost = stats.trend.some((p) => (p.total_cost_usd ?? 0) > 0);

  return (
    <div className="flex flex-col gap-4">
      {/* Hero: pass-rate trend */}
      {hasTrend && (
        <ChartCard title="Başarı oranı trendi">
          <TrendChart points={stats.trend} />
        </ChartCard>
      )}

      {/* Daily activity + cost */}
      {(hasActivity || hasCost) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {hasActivity && (
            <ChartCard title="Günlük aktivite — son 14 gün">
              <DailyBars data={stats.daily_activity!} />
            </ChartCard>
          )}
          {hasCost && (
            <ChartCard title="Run başına maliyet trendi">
              <CostChart points={stats.trend} />
            </ChartCard>
          )}
        </div>
      )}

      {/* Latency histogram */}
      {hasLatency && (
        <ChartCard title="Gecikme dağılımı">
          <LatencyHistogram dist={stats.latency_dist!} />
        </ChartCard>
      )}

      {/* Leaderboards — 3 yan yana */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <ChartCard title={`Agent başarı sıralaması · ${stats.agents_evaluated} agent`}>
          {topAgents.length === 0 ? (
            <Empty text="Agent test verisi yok." />
          ) : (
            <div className="flex flex-col gap-2 py-1">
              {topAgents.map((a) => (
                <Link key={a.agent_id} href={`/agents/${a.agent_id}/performance`} className="group">
                  <BarRow label={a.name} value={a.pass_rate ?? 0} sub={fmtPct(a.pass_rate)} color={barColor(a.pass_rate)} />
                </Link>
              ))}
            </div>
          )}
        </ChartCard>

        {hasUsage ? (
          <ChartCard title="En çok kullanılan agentlar">
            <UsageLeaderboard usage={stats.agent_usage!} />
          </ChartCard>
        ) : (
          <ChartCard title="Özet">
            <div className="flex flex-col gap-3 py-1">
              <BigStat label="Değerlendirilen agent" value={`${stats.agents_evaluated} / ${stats.counts.agents}`} />
              <BigStat label="Değerlendirilen ekip" value={`${stats.teams_evaluated} / ${stats.counts.teams ?? 0}`} />
              <BigStat label="Başarılı run oranı" value={fmtPct(stats.success_run_rate)} />
              <BigStat label="Judge skoru (ort.)" value={stats.avg_judge_score != null ? stats.avg_judge_score.toFixed(2) : "—"} />
            </div>
          </ChartCard>
        )}

        {topTeams.length > 0 ? (
          <ChartCard title={`Ekip sıralaması · ${stats.teams_evaluated} ekip`}>
            <div className="flex flex-col gap-2 py-1">
              {topTeams.map((t) => (
                <Link key={t.team_id} href={`/teams/${t.team_id}`} className="group">
                  <BarRow label={t.name} value={t.success_rate ?? 0} sub={fmtPct(t.success_rate)} color={barColor(t.success_rate)} />
                </Link>
              ))}
            </div>
          </ChartCard>
        ) : (
          <ChartCard title="Genel">
            <div className="flex flex-col gap-3 py-1">
              <BigStat label="Toplam run" value={String(stats.counts.total_runs)} />
              <BigStat label="Tamamlanan" value={String(stats.counts.completed_runs)} />
              <BigStat label="Ort. gecikme" value={fmtDur(stats.avg_latency_ms)} />
            </div>
          </ChartCard>
        )}
      </div>

      {/* Summary donuts */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ChartCard title="Başarılı run oranı">
          <div className="flex items-center justify-center py-2">
            <Donut value={stats.success_run_rate ?? 0} />
          </div>
        </ChartCard>
        <ChartCard title="Judge skoru (ort.)">
          <div className="flex items-center justify-center py-2">
            <Donut value={stats.avg_judge_score ?? 0} label={stats.avg_judge_score != null ? stats.avg_judge_score.toFixed(2) : "—"} color="#818cf8" />
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

// ── Charts ───────────────────────────────────────────────────

function AreaPath({
  values,
  color,
  gradientId,
  height = 80,
}: {
  values: number[];
  color: string;
  gradientId: string;
  height?: number;
}) {
  const W = 560, H = height;
  const n = values.length;
  if (n < 2) return null;
  const max = Math.max(...values, 0.001);
  const px = (i: number) => ((i / (n - 1)) * W).toFixed(1);
  const py = (v: number) => (H - (Math.max(0, v) / max) * H * 0.88 - H * 0.06).toFixed(1);
  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${px(i)},${py(v)}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.38" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={px(n - 1)} cy={py(values[n - 1])} r="2.5" fill={color} />
    </svg>
  );
}

function TrendChart({ points }: { points: SuiteTrendPoint[] }) {
  const pts = points.slice(-25);
  if (pts.length < 2) return <Empty text="Trend için yeterli veri yok." />;
  const latest = pts[pts.length - 1];
  const prev = pts[pts.length - 2];
  const trendDiff =
    latest.pass_rate != null && prev.pass_rate != null
      ? latest.pass_rate - prev.pass_rate
      : null;
  const avgRate = pts.reduce((s, p) => s + (p.pass_rate ?? 0), 0) / pts.length;
  const vals = pts.map((p) => p.pass_rate ?? 0);

  return (
    <div>
      <div className="mb-3 flex items-end gap-3">
        <span className="text-3xl font-bold text-zinc-100">{fmtPct(latest.pass_rate)}</span>
        {trendDiff != null && Math.abs(trendDiff) > 0.001 && (
          <span className={cn("mb-0.5 text-xs font-medium", trendDiff > 0 ? "text-emerald-400" : "text-red-400")}>
            {trendDiff > 0 ? "↑" : "↓"} {Math.abs(Math.round(trendDiff * 100))}pp
          </span>
        )}
        <span className="mb-0.5 ml-auto text-[11px] text-zinc-600">
          ort. {Math.round(avgRate * 100)}% · son {pts.length} run
        </span>
      </div>
      <AreaPath values={vals} color="#6366f1" gradientId="grad-pass" height={88} />
    </div>
  );
}

function CostChart({ points }: { points: SuiteTrendPoint[] }) {
  const pts = points.slice(-25);
  if (pts.length < 2) return <Empty text="Yeterli veri yok." />;
  const costs = pts.map((p) => p.total_cost_usd ?? 0);
  const totalCost = costs.reduce((s, c) => s + c, 0);
  const latest = costs[costs.length - 1];

  return (
    <div>
      <div className="mb-3 flex items-end gap-3">
        <span className="text-xl font-bold text-zinc-100">{fmtUsd(latest)}</span>
        <span className="text-[11px] text-zinc-500">son run</span>
        <span className="mb-0.5 ml-auto text-[11px] text-zinc-600">
          toplam {fmtUsd(totalCost)} · son {pts.length} run
        </span>
      </div>
      <AreaPath values={costs} color="#f59e0b" gradientId="grad-cost" height={64} />
    </div>
  );
}

function DailyBars({ data }: { data: DailyActivityPoint[] }) {
  if (!data.length) return <Empty text="Son 14 günde run yok." />;
  const max = Math.max(...data.map((d) => d.total), 1);
  return (
    <div>
      <div className="flex items-end gap-1" style={{ height: 72 }}>
        {data.map((d) => {
          const h = Math.max((d.total / max) * 64, d.total > 0 ? 3 : 0);
          const rate = d.total > 0 ? d.passed / d.total : null;
          const bg =
            rate == null || d.total === 0
              ? "#3f3f46"
              : rate >= 0.9
              ? "#34d399"
              : rate >= 0.5
              ? "#fbbf24"
              : "#f87171";
          return (
            <div key={d.day} className="group relative flex flex-1 flex-col justify-end" style={{ height: 72 }}>
              <div
                className="w-full rounded-t-sm"
                style={{ height: Math.max(h, 1), backgroundColor: bg, opacity: d.total > 0 ? 0.75 : 0.15 }}
              />
              {d.total > 0 && (
                <div className="pointer-events-none absolute -top-9 left-1/2 z-10 -translate-x-1/2 rounded bg-zinc-800 px-1.5 py-1 text-[10px] text-zinc-200 opacity-0 shadow transition-opacity group-hover:opacity-100 whitespace-nowrap">
                  {d.day.slice(5)} · {d.total} run
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex items-center gap-4 text-[10px] text-zinc-600">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-emerald-500/70" /> ≥90%
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-amber-500/70" /> ≥50%
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-red-400/70" /> &lt;50%
        </span>
      </div>
    </div>
  );
}

function LatencyHistogram({ dist }: { dist: LatencyBucket[] }) {
  const max = Math.max(...dist.map((d) => d.count), 1);
  const total = dist.reduce((s, d) => s + d.count, 0);
  const COLORS = ["#34d399", "#6366f1", "#fbbf24", "#f87171"];
  return (
    <div className="flex items-end justify-between gap-3" style={{ height: 88 }}>
      {dist.map((d, i) => {
        const h = Math.max((d.count / max) * 68, d.count > 0 ? 4 : 0);
        const pct = total > 0 ? Math.round((d.count / total) * 100) : 0;
        return (
          <div key={d.bucket} className="flex flex-1 flex-col items-center gap-1">
            <span className="text-[11px] text-zinc-500">{d.count > 0 ? `${pct}%` : "—"}</span>
            <div
              className="w-full rounded-t-sm"
              style={{ height: h, backgroundColor: COLORS[i], opacity: 0.75 }}
            />
            <span className="text-[10px] text-zinc-600">{d.bucket}</span>
          </div>
        );
      })}
    </div>
  );
}

function UsageLeaderboard({ usage }: { usage: AgentUsagePoint[] }) {
  const maxRuns = Math.max(...usage.map((u) => u.runs), 1);
  return (
    <div className="flex flex-col gap-2 py-1">
      {usage.slice(0, 6).map((u, i) => (
        <Link
          key={u.agent_id}
          href={`/agents/${u.agent_id}/performance`}
          className="group flex items-center gap-2 text-xs"
        >
          <span className="w-4 shrink-0 text-right text-[11px] text-zinc-600 tabular-nums">{i + 1}</span>
          <span className="w-28 truncate text-zinc-300 transition-colors group-hover:text-zinc-100">
            {u.name}
          </span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-1.5 rounded-full bg-indigo-500"
              style={{ width: `${(u.runs / maxRuns) * 100}%` }}
            />
          </div>
          <span className="w-12 shrink-0 text-right text-zinc-500">{u.runs}</span>
        </Link>
      ))}
    </div>
  );
}

// ── Agent / Team detail views ─────────────────────────────────

function AgentView({ entry, agentId }: { entry: OrgLeaderboardEntry | null; agentId: string }) {
  return (
    <div className="flex flex-col gap-4">
      {entry ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <KpiCard label="Başarı oranı" value={fmtPct(entry.pass_rate)} color={rateColor(entry.pass_rate)} />
          <KpiCard label="Test case" value={String(entry.total_cases)} />
          <div className="flex items-center justify-center rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
            <Donut value={entry.pass_rate ?? 0} size={84} />
          </div>
        </div>
      ) : (
        <Empty text="Bu agent için henüz test verisi yok. Test Suite çalıştırınca KPI'lar burada görünür." />
      )}
      <Link href={`/agents/${agentId}/performance`} className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300">
        Detaylı performans paneli <ChevronRight size={13} />
      </Link>
    </div>
  );
}

function TeamView({ entry, teamId }: { entry: TeamLeaderboardEntry | null; teamId: string }) {
  return (
    <div className="flex flex-col gap-4">
      {entry ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <KpiCard label="Başarı oranı" value={fmtPct(entry.success_rate)} color={rateColor(entry.success_rate)} />
          <KpiCard label="Çalıştırma" value={String(entry.total_runs)} />
          <KpiCard label="Üye" value={String(entry.members)} />
          <KpiCard label="Ort. süre" value={fmtDur(entry.avg_duration_ms)} />
        </div>
      ) : (
        <Empty text="Bu ekip için henüz çalıştırma verisi yok." />
      )}
      <Link href={`/teams/${teamId}`} className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300">
        Ekip detayı & çalıştırmalar <ChevronRight size={13} />
      </Link>
    </div>
  );
}

// ── Arama + kart grid ─────────────────────────────────────────

function PickGrid({ q, setQ, placeholder, items, onPick, icon: Icon }: {
  q: string; setQ: (v: string) => void; placeholder: string;
  items: { id: string; name: string; sub: string; rate: number | null }[];
  onPick: (id: string) => void; icon: typeof Bot;
}) {
  const filtered = items.filter((i) => i.name.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder}
          className="w-full rounded-lg border border-zinc-800 bg-zinc-950 py-2 pl-9 pr-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-700 focus:outline-none"
        />
      </div>
      {filtered.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">Eşleşme yok.</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((i) => (
            <button key={i.id} onClick={() => onPick(i.id)}
              className="flex items-center gap-2.5 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3 text-left transition-colors hover:border-indigo-500/40 hover:bg-zinc-900/70">
              <Icon size={16} className="shrink-0 text-indigo-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-zinc-200">{i.name}</p>
                <p className="truncate text-[11px] text-zinc-600">{i.sub}</p>
              </div>
              {i.rate != null && (
                <span className={cn("shrink-0 text-xs font-semibold", rateColor(i.rate))}>{fmtPct(i.rate)}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SelectedHeader({ name, onBack, children }: { name: string; onBack: () => void; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <button onClick={onBack} className="inline-flex w-fit items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Tümü
      </button>
      <p className="-mb-1 text-sm font-medium text-zinc-200">{name}</p>
      {children}
    </div>
  );
}

// ── Primitives ───────────────────────────────────────────────

function ScopeTab({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Zap; label: string }) {
  return (
    <button onClick={onClick}
      className={cn("flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
        active ? "bg-indigo-500/15 text-indigo-200" : "text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300")}>
      <Icon size={13} />{label}
    </button>
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

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wide text-zinc-500">{title}</p>
      {children}
    </div>
  );
}

function KpiCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <p className={cn("text-xl font-semibold", color ?? "text-zinc-100")}>{value}</p>
      <p className="mt-0.5 text-[11px] text-zinc-500">{label}</p>
    </div>
  );
}

function BigStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className="text-sm font-semibold text-zinc-100">{value}</span>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-xl border border-dashed border-zinc-800 py-6 text-center text-xs text-zinc-600">{text}</p>;
}

function BarRow({ label, value, sub, color = "bg-indigo-500" }: { label: string; value: number; sub: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs transition-opacity group-hover:opacity-80">
      <span className="w-28 truncate text-zinc-300">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div className={cn("h-1.5 rounded-full", color)} style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%` }} />
      </div>
      <span className="w-10 text-right text-zinc-400">{sub}</span>
    </div>
  );
}

function Donut({ value, label, color = "#34d399", size = 110 }: { value: number; label?: string; color?: string; size?: number }) {
  const v = Math.max(0, Math.min(1, value));
  const stroke = 11;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#27272a" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - v)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-zinc-100" style={{ fontSize: 18, fontWeight: 600 }}>
        {label ?? `${Math.round(v * 100)}%`}
      </text>
    </svg>
  );
}

