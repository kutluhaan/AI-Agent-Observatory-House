"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus, X } from "lucide-react";
import { api, ApiError, type Agent, type RoleInfo, type Team, type TeamMemberInput } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { Alert } from "@/components/ui/alert";

export default function NewTeamPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [members, setMembers] = useState<TeamMemberInput[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Agent[]>("/agents").then(setAgents).catch(() => {});
    api.get<RoleInfo[]>("/teams/roles").then((r) => {
      setRoles(r);
      // varsayılan: bir coordinator satırı
      const coord = r.find((x) => x.role === "coordinator");
      if (coord) setMembers([{ agent_id: "", role: "coordinator", role_prompt: coord.default_prompt }]);
    }).catch(() => {});
  }, []);

  function addMember() {
    const worker = roles.find((x) => x.role === "worker") ?? roles[0];
    setMembers((m) => [...m, { agent_id: "", role: worker?.role ?? "worker", role_prompt: worker?.default_prompt ?? "" }]);
  }

  function setMember(i: number, patch: Partial<TeamMemberInput>) {
    setMembers((ms) => ms.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));
  }

  function setRole(i: number, role: string) {
    const info = roles.find((x) => x.role === role);
    setMember(i, { role, role_prompt: info?.default_prompt ?? "" });
  }

  const coordCount = members.filter((m) => m.role === "coordinator").length;
  const valid = name.trim() && members.length > 0 && members.every((m) => m.agent_id) && coordCount === 1;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const team = await api.post<Team>("/teams", { name, description: description || null, members });
      router.replace(`/teams/${team.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Oluşturulamadı.");
      setSubmitting(false);
    }
  }

  const agentOptions = agents.map((a) => ({ value: a.id, label: `${a.name} (${a.provider})` }));
  const roleOptions = roles.map((r) => ({ value: r.role, label: r.label }));

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <Link href="/teams" className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Ekipler
      </Link>
      <h1 className="mb-6 text-xl font-semibold text-zinc-100">Yeni ekip</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <Alert variant="error">{error}</Alert>}

        <Input label="Ad" value={name} onChange={(e) => setName(e.target.value)} placeholder="Araştırma ekibi" required />
        <Input label="Açıklama" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Opsiyonel" />

        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Üyeler {coordCount !== 1 && <span className="text-amber-400">(tam 1 coordinator gerekli)</span>}
          </p>
          <Button type="button" size="sm" variant="outline" onClick={addMember}><Plus size={13} />Üye ekle</Button>
        </div>

        {members.map((m, i) => (
          <div key={i} className="flex flex-col gap-2 rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
            <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
              <Dropdown label="Agent" value={m.agent_id} options={[{ value: "", label: "— seç —" }, ...agentOptions]} onChange={(v) => setMember(i, { agent_id: v })} />
              <Dropdown label="Rol" value={m.role} options={roleOptions} onChange={(v) => setRole(i, v)} />
              <button type="button" onClick={() => setMembers((ms) => ms.filter((_, idx) => idx !== i))} className="mb-1.5 rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-red-400" title="Kaldır">
                <X size={14} />
              </button>
            </div>
            <Textarea label="Rol promptu" value={m.role_prompt ?? ""} onChange={(e) => setMember(i, { role_prompt: e.target.value })} rows={3} className="text-xs" />
          </div>
        ))}

        <Button type="submit" size="lg" loading={submitting} disabled={!valid} className="mt-2">Ekibi oluştur</Button>
      </form>
    </div>
  );
}
