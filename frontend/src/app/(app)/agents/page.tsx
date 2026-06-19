"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Plus, MessageSquare, ShieldCheck } from "lucide-react";
import { api, type Agent } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Agent[]>("/agents")
      .then(setAgents)
      .catch(() => setError("Failed to load agents."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Agents</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Build and run AI agents, then watch them in the trace view.
          </p>
        </div>
        <Link href="/agents/new">
          <Button size="sm">
            <Plus size={14} />
            New agent
          </Button>
        </Link>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <Bot size={28} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">No agents yet.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Create your first agent to start chatting.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {agents.map((agent) => (
            <Link
              key={agent.id}
              href={`/agents/${agent.id}/chat`}
              className="group flex flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex items-start justify-between">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10">
                  <Bot size={17} className="text-indigo-400" />
                </div>
                <div className="flex items-center gap-1.5">
                  {!agent.is_active && <Badge variant="zinc">inactive</Badge>}
                  {agent.hitl_tool_names.length > 0 && (
                    <Badge variant="amber">
                      <ShieldCheck size={10} />
                      HITL
                    </Badge>
                  )}
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-100">{agent.name}</p>
                <p className="mt-0.5 line-clamp-2 text-xs text-zinc-500">
                  {agent.description || agent.system_prompt}
                </p>
              </div>
              <div className="flex items-center justify-between border-t border-zinc-800/60 pt-3">
                <span className="text-[11px] text-zinc-600">
                  {agent.provider} · {agent.model}
                </span>
                <span className="flex items-center gap-1 text-[11px] text-indigo-400 opacity-0 transition-opacity group-hover:opacity-100">
                  <MessageSquare size={11} />
                  Chat
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
