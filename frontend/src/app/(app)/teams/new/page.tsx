"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, X, Users, GripVertical, Settings, ChevronDown, MousePointerClick } from "lucide-react";
import { api, ApiError, type Agent, type Team } from "@/lib/api";
import { roleIcon, roleColor } from "@/lib/team-roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

interface RoleInfo { role: string; label: string; default_prompt: string }
interface Member { agent: Agent; role: string }

export default function NewTeamPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [sharedInstructions, setSharedInstructions] = useState("");
  const [maxDelegations, setMaxDelegations] = useState(10);
  const [runTimeout, setRunTimeout] = useState(600);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Agent[]>("/agents").then(setAgents).catch(() => {});
    api.get<RoleInfo[]>("/teams/roles").then(setRoles).catch(() => {});
  }, []);

  const memberIds = new Set(members.map((m) => m.agent.id));
  const coordCount = members.filter((m) => m.role === "coordinator").length;
  const valid = name.trim() && members.length > 0 && coordCount === 1;

  function defaultRole(): string {
    // İlk eklenen coordinator olsun (tam 1 gerekir), sonrakiler worker
    return members.some((m) => m.role === "coordinator") ? "worker" : "coordinator";
  }

  function addAgent(agentId: string) {
    if (memberIds.has(agentId)) return;
    const agent = agents.find((a) => a.id === agentId);
    if (!agent) return;
    setMembers((m) => [...m, { agent, role: defaultRole() }]);
  }

  function setRole(agentId: string, role: string) {
    setMembers((m) => m.map((x) => (x.agent.id === agentId ? { ...x, role } : x)));
  }

  function removeMember(agentId: string) {
    setMembers((m) => m.filter((x) => x.agent.id !== agentId));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const members_payload = members.map((m, i) => ({
        agent_id: m.agent.id,
        role: m.role,
        // Rol promptu = o rolün varsayılanı (UI alanı yok); davranış agent'ın system_prompt'undan gelir
        role_prompt: roles.find((r) => r.role === m.role)?.default_prompt ?? "",
        position: i,
      }));
      const team = await api.post<Team>("/teams", {
        name, description: description || null, members: members_payload,
        shared_instructions: sharedInstructions || null,
        max_delegations: maxDelegations, run_timeout_seconds: runTimeout,
      });
      router.replace(`/teams/${team.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Oluşturulamadı.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <Link href="/teams" className="mb-5 inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Ekipler
      </Link>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Ad + açıklama */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Input label="Ekip adı" value={name} onChange={(e) => setName(e.target.value)} placeholder="Araştırma Ekibi" />
          <Input label="Açıklama (opsiyonel)" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {/* Sürükle-bırak alanı: sol geniş üyeler · sağ agent listesi */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_300px]">
          {/* Sol: ekip üyeleri (drop zone) */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); addAgent(e.dataTransfer.getData("agentId")); }}
            className={cn(
              "min-h-[360px] rounded-xl border-2 border-dashed p-4 transition-colors",
              dragOver ? "border-indigo-500/60 bg-indigo-500/5" : "border-zinc-800 bg-zinc-900/20",
            )}
          >
            <div className="mb-3 flex items-center gap-2">
              <Users size={15} className="text-indigo-400" />
              <span className="text-sm font-medium text-zinc-200">Ekip Üyeleri</span>
              <span className="text-[11px] text-zinc-600">{members.length} üye</span>
              {members.length > 0 && coordCount !== 1 && (
                <span className="ml-auto text-[11px] text-amber-400">Tam 1 coordinator gerekli ({coordCount})</span>
              )}
            </div>

            {members.length === 0 ? (
              <div className="flex h-[280px] flex-col items-center justify-center gap-2 text-center text-zinc-600">
                <MousePointerClick size={26} className="text-zinc-700" />
                <p className="text-sm">Sağdaki agent&apos;ları buraya <span className="text-zinc-400">sürükle-bırak</span></p>
                <p className="text-xs">Bırakınca rolünü seçersin; role göre ikonu değişir.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {members.map((m) => {
                  const RI = roleIcon(m.role);
                  return (
                    <div key={m.agent.id} className="flex items-center gap-3 rounded-lg border border-zinc-800/70 bg-zinc-900/50 px-3 py-2.5">
                      <RI size={18} className={cn("shrink-0", roleColor(m.role))} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-zinc-200">{m.agent.name}</p>
                        <p className="truncate text-[11px] text-zinc-600">{m.agent.provider} · {m.agent.model}</p>
                      </div>
                      {/* Drop'ta çıkan TEK alan: rol seçimi */}
                      <select
                        value={m.role}
                        onChange={(e) => setRole(m.agent.id, e.target.value)}
                        className="rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
                      >
                        {roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}
                      </select>
                      <button type="button" onClick={() => removeMember(m.agent.id)}
                        className="rounded-md p-1 text-zinc-500 hover:bg-red-500/10 hover:text-red-400" title="Çıkar">
                        <X size={14} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Sağ: mevcut agent'lar (scrollable, draggable) */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-3">
            <p className="mb-2 text-[11px] uppercase tracking-wide text-zinc-500">Mevcut Agent&apos;lar</p>
            <div className="flex max-h-[340px] flex-col gap-1.5 overflow-y-auto pr-1">
              {agents.length === 0 ? (
                <p className="py-6 text-center text-xs text-zinc-600">Önce agent oluştur.</p>
              ) : (
                agents.map((a) => {
                  const added = memberIds.has(a.id);
                  return (
                    <div
                      key={a.id}
                      draggable={!added}
                      onDragStart={(e) => e.dataTransfer.setData("agentId", a.id)}
                      onDoubleClick={() => addAgent(a.id)}
                      title={added ? "Zaten ekli" : "Sürükle ya da çift tıkla"}
                      className={cn(
                        "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors",
                        added
                          ? "cursor-default border-zinc-800/50 opacity-40"
                          : "cursor-grab border-zinc-800/70 hover:border-indigo-500/40 hover:bg-zinc-900/60 active:cursor-grabbing",
                      )}
                    >
                      <GripVertical size={13} className="shrink-0 text-zinc-600" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-zinc-200">{a.name}</p>
                        <p className="truncate text-[10px] text-zinc-600">{a.provider} · {a.model}</p>
                      </div>
                      {added && <span className="shrink-0 text-[10px] text-green-400">ekli</span>}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Ekip ayarları (bütçe) — katlanır */}
        <div>
          <button type="button" onClick={() => setShowSettings((s) => !s)}
            className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500 hover:text-zinc-300">
            <Settings size={12} className={cn("transition-transform", showSettings && "rotate-90")} />
            Ekip ayarları (prompt & bütçe)
            <ChevronDown size={12} className={cn("transition-transform", showSettings && "rotate-180")} />
          </button>
          {showSettings && (
            <div className="mt-3 flex flex-col gap-3 rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
              <Textarea label="Ekip promptu (tüm üyelere eklenir)" value={sharedInstructions}
                onChange={(e) => setSharedInstructions(e.target.value)} rows={2} className="text-xs"
                placeholder="Ortak kurallar: kısa/odaklı çalış, az arama yap…" />
              <div className="grid grid-cols-2 gap-3">
                <Input label="Max delege" type="number" value={String(maxDelegations)}
                  onChange={(e) => setMaxDelegations(Math.max(1, Math.min(50, Number(e.target.value) || 10)))} />
                <Input label="Üst süre (sn)" type="number" value={String(runTimeout)}
                  onChange={(e) => setRunTimeout(Math.max(30, Math.min(3600, Number(e.target.value) || 600)))} />
              </div>
            </div>
          )}
        </div>

        <div>
          <Button type="submit" size="lg" loading={submitting} disabled={!valid}>Ekibi oluştur</Button>
          {!valid && members.length > 0 && coordCount !== 1 && (
            <span className="ml-3 text-xs text-amber-400">Tam 1 coordinator olmalı.</span>
          )}
        </div>
      </form>
    </div>
  );
}
