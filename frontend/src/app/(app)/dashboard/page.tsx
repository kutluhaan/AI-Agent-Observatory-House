"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Building2, Zap, Users, Search, ArrowLeft, Bot } from "lucide-react";
import { useAuth } from "@/contexts/auth";
import { api, type OrgDashboard, type OrgLeaderboardEntry, type TeamLeaderboardEntry, type Agent, type Team } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtPct(v: number | null): string { return v == null ? "—" : `${Math.round(v * 100)}%`; }
function fmtUsd(v: number | null): string { if (v == null) return "—"; return `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`; }
function fmtDur(ms: number | null): string { if (ms == null) return "—"; const s = ms / 1000; return s < 60 ? `${s.toFixed(1)}s` : `${(s / 60).toFixed(1)}dk`; }
function rateColor(v: number | null): string { if (v == null) return "text-zinc-500"; return v >= 0.99 ? "text-green-400" : v >= 0.6 ? "text-amber-400" : "text-red-400"; }
function barColor(v: number | null): string { if (v == null) return "bg-zinc-600"; return v >= 0.99 ? "bg-green-500" : v >= 0.6 ? "bg-amber-500" : "bg-red-500"; }

type Scope = "org" | "agent" | "team";

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

  // id → KPI eşlemesi (leaderboard yalnız değerlendirilmişleri içerir)
  const agentKpi = useMemo(() => new Map(stats?.leaderboard.map((a) => [a.agent_id, a]) ?? []), [stats]);
  const teamKpi = useMemo(() => new Map(stats?.team_leaderboard.map((t) => [t.team_id, t]) ?? []), [stats]);

  function pickScope(s: Scope) { setScope(s); setQ(""); }

  if (!user?.org_id) return null;
  const firstName = user.full_name?.split(" ")[0] ?? "there";
  const hasData = stats && (stats.counts.total_runs > 0 || (stats.counts.teams ?? 0) > 0);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-12">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-zinc-100">Merhaba, {firstName}</h1>
        <p className="mt-1.5 text-sm text-zinc-500">{user.org_name ?? user.org_slug} workspace</p>
      </div>

      {/* Org metrik şeridi — her zaman görünür */}
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

// ── Arama + kart grid (agent/ekip seçimi) ───────────────────

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

// ── Org görünümü: grafikler ─────────────────────────────────

function OrgView({ stats }: { stats: OrgDashboard }) {
  const topAgents = stats.leaderboard.slice(0, 6);
  const topTeams = stats.team_leaderboard.slice(0, 6);
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <ChartCard title="Başarılı run oranı">
          <div className="flex items-center justify-center py-2"><Donut value={stats.success_run_rate ?? 0} /></div>
        </ChartCard>
        <ChartCard title="Değerlendirme">
          <div className="flex h-full flex-col justify-center gap-3 py-2">
            <BigStat label="Agent (değerlendirilen)" value={`${stats.agents_evaluated}/${stats.counts.agents}`} />
            <BigStat label="Ekip (değerlendirilen)" value={`${stats.teams_evaluated}/${stats.counts.teams ?? 0}`} />
          </div>
        </ChartCard>
        <ChartCard title="Judge skoru (ort.)">
          <div className="flex items-center justify-center py-2">
            <Donut value={stats.avg_judge_score ?? 0} label={stats.avg_judge_score != null ? stats.avg_judge_score.toFixed(2) : "—"} color="#818cf8" />
          </div>
        </ChartCard>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartCard title={`Agent başarı sıralaması · ${stats.agents_evaluated} değerlendirildi`}>
          {topAgents.length === 0 ? <Empty text="Agent test verisi yok." /> : (
            <div className="flex flex-col gap-2 py-1">
              {topAgents.map((a) => (
                <Link key={a.agent_id} href={`/agents/${a.agent_id}/performance`} className="group">
                  <BarRow label={a.name} value={a.pass_rate ?? 0} sub={fmtPct(a.pass_rate)} color={barColor(a.pass_rate)} />
                </Link>
              ))}
            </div>
          )}
        </ChartCard>
        <ChartCard title={`Ekip başarı sıralaması · ${stats.teams_evaluated} değerlendirildi`}>
          {topTeams.length === 0 ? <Empty text="Ekip verisi yok." /> : (
            <div className="flex flex-col gap-2 py-1">
              {topTeams.map((t) => (
                <Link key={t.team_id} href={`/teams/${t.team_id}`} className="group">
                  <BarRow label={t.name} value={t.success_rate ?? 0} sub={fmtPct(t.success_rate)} color={barColor(t.success_rate)} />
                </Link>
              ))}
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}

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

// ── Yapı taşları ────────────────────────────────────────────

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
      <p className="mb-2 text-[11px] uppercase tracking-wide text-zinc-500">{title}</p>
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

function BarRow({ label, value, sub, color = "bg-indigo-500" }: { label: string; value: number; sub: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs transition-opacity group-hover:opacity-80">
      <span className="w-28 truncate text-zinc-300">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div className={cn("h-2 rounded-full", color)} style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%` }} />
      </div>
      <span className="w-10 text-right text-zinc-400">{sub}</span>
    </div>
  );
}
