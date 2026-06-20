"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api, type Agent } from "@/lib/api";
import { AgentForm, type AgentFormValues } from "@/components/agent-form";

export default function NewAgentPage() {
  const router = useRouter();

  async function handleCreate(values: AgentFormValues) {
    const agent = await api.post<Agent>("/agents", values);
    router.replace(`/agents/${agent.id}/chat`);
  }

  return (
    <div className="mx-auto w-full max-w-xl px-6 py-10">
      <Link
        href="/agents"
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Agents
      </Link>

      <h1 className="mb-6 text-xl font-semibold text-zinc-100">New agent</h1>

      <AgentForm submitLabel="Create agent" onSubmit={handleCreate} />
    </div>
  );
}
