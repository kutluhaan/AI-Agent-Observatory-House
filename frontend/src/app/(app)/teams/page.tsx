"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Users, Plus, Trash2 } from "lucide-react";
import { api, ApiError, type Team } from "@/lib/api";
import { roleIcon } from "@/lib/team-roles";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function TeamsPage() {
  const router = useRouter();
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Team[]>("/teams").then(setTeams).catch(() => setError("Yüklenemedi.")).finally(() => setLoading(false));
  }, []);

  async function remove(t: Team) {
    if (!window.confirm(`"${t.name}" ekibini sil?`)) return;
    try {
      await api.delete(`/teams/${t.id}`);
      setTeams((p) => p.filter((x) => x.id !== t.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Silinemedi.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Agent Ekipleri</h1>
          <p className="mt-1 text-sm text-zinc-500">Rollü çok-agent ekipleri: Coordinator delege eder, üyeler işbirliği yapar.</p>
        </div>
        <Link href="/teams/new">
          <Button size="sm"><Plus size={14} />Yeni ekip</Button>
        </Link>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16"><Spinner className="h-5 w-5" /></div>
      ) : teams.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <Users size={28} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">Henüz ekip yok.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {teams.map((t) => (
            <div
              key={t.id}
              onClick={() => router.push(`/teams/${t.id}/chat`)}
              className="group relative flex cursor-pointer flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex items-start justify-between">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10">
                  <Users size={17} className="text-indigo-400" />
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); remove(t); }}
                  title="Sil"
                  className="rounded-md p-1 text-zinc-600 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
                >
                  <Trash2 size={13} />
                </button>
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-100">{t.name}</p>
                {t.description && <p className="mt-0.5 line-clamp-2 text-xs text-zinc-500">{t.description}</p>}
              </div>
              <div className="mt-auto flex flex-col gap-1.5 border-t border-zinc-800/60 pt-3">
                <span className="text-[10px] uppercase tracking-wide text-zinc-600">{t.members.length} üye</span>
                <div className="flex flex-wrap gap-1">
                  {t.members.map((m) => {
                    const RI = roleIcon(m.role);
                    return (
                      <Badge key={m.id} variant={m.role === "coordinator" ? "indigo" : "zinc"}>
                        <RI size={10} />
                        <span className="font-medium">{m.agent_name ?? "—"}</span>
                        <span className="text-zinc-500">· {m.role}</span>
                      </Badge>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
