"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, FolderTree } from "lucide-react";
import { api, ApiError, type Agent, type AgentTool } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

const PROVIDERS = [
  { value: "gemini", label: "Google Gemini" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "ollama", label: "Ollama (local)" },
];

const MODELS_BY_PROVIDER: Record<string, string[]> = {
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini"],
  anthropic: ["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"],
  ollama: ["llama3.1", "llama3.2", "qwen2.5", "mistral"],
};

export default function NewAgentPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-2.5-flash");
  const [temperature, setTemperature] = useState(0.7);
  const [tools, setTools] = useState<AgentTool[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [hitl, setHitl] = useState<Set<string>>(new Set());
  const [fileSystem, setFileSystem] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<AgentTool[]>("/agents/tools").then(setTools).catch(() => {});
  }, []);

  function toggleTool(toolName: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(toolName)) {
        next.delete(toolName);
        setHitl((h) => {
          const hn = new Set(h);
          hn.delete(toolName);
          return hn;
        });
      } else {
        next.add(toolName);
      }
      return next;
    });
  }

  function toggleHitl(toolName: string) {
    setHitl((prev) => {
      const next = new Set(prev);
      if (next.has(toolName)) next.delete(toolName);
      else next.add(toolName);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const agent = await api.post<Agent>("/agents", {
        name,
        system_prompt: systemPrompt,
        provider,
        model,
        temperature,
        tool_names: Array.from(selected),
        hitl_tool_names: Array.from(hitl),
        file_system_enabled: fileSystem,
      });
      router.replace(`/agents/${agent.id}/chat`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create agent.",
      );
      setSubmitting(false);
    }
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

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <Alert variant="error">{error}</Alert>}

        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Research assistant"
          required
        />

        <Textarea
          label="System prompt"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="You are a helpful assistant..."
          rows={4}
          required
        />

        <div className="grid grid-cols-2 gap-3">
          <Dropdown
            label="Provider"
            value={provider}
            options={PROVIDERS}
            onChange={(v) => {
              setProvider(v);
              setModel(MODELS_BY_PROVIDER[v]?.[0] ?? "");
            }}
          />
          <Dropdown
            label="Model"
            value={model}
            options={(MODELS_BY_PROVIDER[provider] ?? []).map((m) => ({ value: m, label: m }))}
            onChange={setModel}
          />
        </div>

        <Input
          label="Temperature"
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={temperature}
          onChange={(e) => setTemperature(parseFloat(e.target.value))}
        />

        {/* Dosya sistemi — açılırsa dosya tool'ları otomatik eklenir */}
        <div
          className={cn(
            "rounded-lg border px-3 py-3 transition-colors",
            fileSystem ? "border-indigo-500/30 bg-indigo-500/5" : "border-zinc-800",
          )}
        >
          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={fileSystem}
              onChange={(e) => setFileSystem(e.target.checked)}
              className="mt-0.5 accent-indigo-500"
            />
            <div className="flex-1">
              <div className="flex items-center gap-1.5">
                <FolderTree size={14} className="text-indigo-400" />
                <span className="text-sm text-zinc-200">Dosya sistemi</span>
              </div>
              <p className="mt-0.5 text-xs text-zinc-500">
                Agent&apos;a izole, kalıcı bir dosya sistemi ver. Açılırsa dosya
                araçları (yaz/oku/düzenle/sil/listele/ara/klasör/taşı) otomatik eklenir.
              </p>
            </div>
          </label>
        </div>

        {tools.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium tracking-wide text-zinc-400">
              Tools
            </span>
            <div className="flex flex-col gap-1.5">
              {tools.map((tool) => {
                const isSelected = selected.has(tool.name);
                const isHitl = hitl.has(tool.name);
                return (
                  <div
                    key={tool.name}
                    className={cn(
                      "rounded-lg border px-3 py-2.5 transition-colors",
                      isSelected
                        ? "border-indigo-500/30 bg-indigo-500/5"
                        : "border-zinc-800 hover:border-zinc-700",
                    )}
                  >
                    <label className="flex cursor-pointer items-start gap-2.5">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleTool(tool.name)}
                        className="mt-0.5 accent-indigo-500"
                      />
                      <div className="flex-1">
                        <p className="text-sm text-zinc-200">{tool.name}</p>
                        <p className="text-xs text-zinc-600">{tool.description}</p>
                      </div>
                    </label>
                    {isSelected && tool.name !== "ask_user" && (
                      <label className="mt-2 flex cursor-pointer items-center gap-2 pl-7 text-xs text-amber-300/80">
                        <input
                          type="checkbox"
                          checked={isHitl}
                          onChange={() => toggleHitl(tool.name)}
                          className="accent-amber-500"
                        />
                        <ShieldCheck size={12} />
                        Require human approval (HITL)
                      </label>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <Button type="submit" size="lg" loading={submitting} className="mt-2">
          Create agent
        </Button>
      </form>
    </div>
  );
}
