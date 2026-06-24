"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, History, RotateCcw, ChevronDown } from "lucide-react";
import { api, ApiError, type Agent, type PromptVersionList } from "@/lib/api";
import { AgentForm, type AgentFormValues } from "@/components/agent-form";
import { Spinner } from "@/components/ui/spinner";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function EditAgentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Agent>(`/agents/${id}`)
      .then(setAgent)
      .catch(() => setError("Agent yüklenemedi."));
  }, [id]);

  async function handleSave(values: AgentFormValues) {
    await api.patch(`/agents/${id}`, values);
    router.replace(`/agents/${id}/chat`);
  }

  return (
    <div className="mx-auto w-full max-w-xl px-6 py-10">
      <Link
        href={`/agents/${id}/chat`}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Sohbete dön
      </Link>

      <h1 className="mb-6 text-xl font-semibold text-zinc-100">Agent&apos;ı düzenle</h1>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {!agent ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : (
        <AgentForm
          initial={{
            name: agent.name,
            system_prompt: agent.system_prompt,
            provider: agent.provider,
            model: agent.model,
            temperature: agent.temperature,
            tool_names: agent.tool_names,
            hitl_tool_names: agent.hitl_tool_names,
            file_system_enabled: agent.file_system_enabled,
            endpoint_url: agent.endpoint_url,
            mcp_tools: agent.mcp_tools,
            custom_tool_ids: agent.custom_tool_ids?.map(String) ?? null,
          }}
          submitLabel="Değişiklikleri kaydet"
          onSubmit={handleSave}
        />
      )}

      {agent && <PromptVersions agentId={id} activeVersion={agent.prompt_version} />}
    </div>
  );
}

// ── Geçmiş sürümler (it.6) ──────────────────────────────────

function PromptVersions({ agentId, activeVersion }: { agentId: string; activeVersion: number }) {
  const [data, setData] = useState<PromptVersionList | null>(null);
  const [open, setOpen] = useState(false);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<PromptVersionList>(`/agents/${agentId}/prompt-versions`).then(setData).catch(() => {});
  }, [agentId]);

  async function restore(v: number) {
    if (!window.confirm(`v${v} sürümüne geri dön? (mevcut config yeni sürüm olarak saklanır)`)) return;
    setRestoring(v);
    setError("");
    try {
      await api.post(`/agents/${agentId}/prompt-versions/${v}/restore`);
      window.location.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Geri yüklenemedi.");
      setRestoring(null);
    }
  }

  if (!data || data.versions.length <= 1) return null;

  return (
    <div className="mt-8">
      <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500 hover:text-zinc-300">
        <History size={13} />
        Geçmiş sürümler ({data.versions.length})
        <ChevronDown size={12} className={cn("transition-transform", open && "rotate-180")} />
      </button>
      {error && <Alert variant="error" className="mt-2">{error}</Alert>}
      {open && (
        <div className="mt-3 overflow-hidden rounded-xl border border-zinc-800/80">
          {data.versions.map((v, i) => (
            <div key={v.version} className={cn("flex items-center gap-3 px-4 py-3", i > 0 && "border-t border-zinc-800/60")}>
              <span className={cn("text-xs font-semibold", v.version === activeVersion ? "text-green-400" : "text-zinc-400")}>v{v.version}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-zinc-400">{v.note ?? "—"} · {v.model}</p>
                <p className="truncate text-[11px] text-zinc-600">{v.system_prompt}</p>
              </div>
              <span className="shrink-0 text-[10px] text-zinc-700">{new Date(v.created_at).toLocaleString()}</span>
              {v.version === activeVersion ? (
                <span className="shrink-0 text-[10px] text-green-400">aktif</span>
              ) : (
                <Button size="sm" variant="outline" onClick={() => restore(v.version)} loading={restoring === v.version}>
                  <RotateCcw size={12} />Geri yükle
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
