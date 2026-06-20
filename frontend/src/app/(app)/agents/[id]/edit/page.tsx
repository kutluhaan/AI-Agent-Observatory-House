"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api, type Agent } from "@/lib/api";
import { AgentForm, type AgentFormValues } from "@/components/agent-form";
import { Spinner } from "@/components/ui/spinner";
import { Alert } from "@/components/ui/alert";

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
          }}
          submitLabel="Değişiklikleri kaydet"
          onSubmit={handleSave}
        />
      )}
    </div>
  );
}
