"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  FolderTree,
  Globe,
  Brain,
  TrendingUp,
  Briefcase,
} from "lucide-react";
import { api, ApiError, type ToolCategory } from "@/lib/api";
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
  { value: "custom", label: "Custom (OpenAI-uyumlu, self-hosted)" },
  { value: "http", label: "External agent (HTTP, OpenAI-uyumlu)" },
];

// Serbest-metin model + endpoint gerektiren provider'lar
const FREE_MODEL_PROVIDERS = new Set(["custom", "http"]);

const MODELS_BY_PROVIDER: Record<string, string[]> = {
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini"],
  anthropic: ["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"],
  ollama: ["qwen3:4b", "llama3.2", "qwen2.5", "mistral"],
};

const CATEGORY_ICONS: Record<string, typeof Globe> = {
  file: FolderTree,
  web: Globe,
  self: Brain,
  finance: TrendingUp,
  operation: Briefcase,
};

export interface AgentFormValues {
  name: string;
  system_prompt: string;
  provider: string;
  model: string;
  temperature: number;
  tool_names: string[];
  hitl_tool_names: string[];
  file_system_enabled: boolean;
  endpoint_url?: string | null;
  endpoint_api_key?: string | null;
}

export function AgentForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial?: Partial<AgentFormValues>;
  submitLabel: string;
  onSubmit: (values: AgentFormValues) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [systemPrompt, setSystemPrompt] = useState(initial?.system_prompt ?? "");
  const [provider, setProvider] = useState(initial?.provider ?? "gemini");
  const [model, setModel] = useState(initial?.model ?? "gemini-2.5-flash");
  const [temperature, setTemperature] = useState(initial?.temperature ?? 0.7);
  const [categories, setCategories] = useState<ToolCategory[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set(initial?.tool_names ?? []));
  const [hitl, setHitl] = useState<Set<string>>(new Set(initial?.hitl_tool_names ?? []));
  const [fileSystem, setFileSystem] = useState(initial?.file_system_enabled ?? false);
  const [endpointUrl, setEndpointUrl] = useState(initial?.endpoint_url ?? "");
  const [endpointApiKey, setEndpointApiKey] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<ToolCategory[]>("/agents/tool-categories").then(setCategories).catch(() => {});
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

  function setCategoryTools(toolNames: string[], on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      toolNames.forEach((n) => (on ? next.add(n) : next.delete(n)));
      return next;
    });
    if (!on) {
      setHitl((prev) => {
        const next = new Set(prev);
        toolNames.forEach((n) => next.delete(n));
        return next;
      });
    }
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
      await onSubmit({
        name,
        system_prompt: systemPrompt,
        provider,
        model,
        temperature,
        tool_names: Array.from(selected),
        hitl_tool_names: Array.from(hitl),
        file_system_enabled: fileSystem,
        // F7.1: http agent endpoint (yalnız http için anlamlı). Key boşsa gönderme (mevcut korunur).
        endpoint_url: provider === "http" ? endpointUrl : null,
        ...(endpointApiKey ? { endpoint_api_key: endpointApiKey } : {}),
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "İşlem başarısız oldu.");
      setSubmitting(false);
    }
  }

  const modelOptions = Array.from(
    new Set([...(MODELS_BY_PROVIDER[provider] ?? []), model].filter(Boolean)),
  ).map((m) => ({ value: m, label: m }));

  return (
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
        {FREE_MODEL_PROVIDERS.has(provider) ? (
          <Input
            label="Model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={provider === "http" ? "external-agent" : "gpt-oss-20b"}
          />
        ) : (
          <Dropdown label="Model" value={model} options={modelOptions} onChange={setModel} />
        )}
      </div>

      {/* F7.1: external HTTP agent — per-agent endpoint */}
      {provider === "http" && (
        <div className="flex flex-col gap-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-3">
          <p className="text-xs text-zinc-400">
            Dış agent&apos;ı <span className="text-zinc-200">OpenAI-uyumlu</span> bir HTTP endpoint
            üzerinden çağırır (POST <code className="text-indigo-300">/chat/completions</code>).
            Endpoint kendi mantığını/araçlarını çalıştırır; platform input gönderir, çıktı alır.
          </p>
          <Input
            label="Endpoint URL (base, OpenAI-uyumlu)"
            value={endpointUrl}
            onChange={(e) => setEndpointUrl(e.target.value)}
            placeholder="http://my-agent:9000/v1"
          />
          <Input
            label="API anahtarı (opsiyonel)"
            type="password"
            value={endpointApiKey}
            onChange={(e) => setEndpointApiKey(e.target.value)}
            placeholder={initial?.endpoint_url ? "•••• (değiştirmek için yaz)" : "gerekmiyorsa boş bırak"}
          />
          <p className="text-[11px] text-zinc-600">
            Docker&apos;dan erişim: aynı makinedeyse <code>host.docker.internal</code>, LAN/uzak
            sunucuysa IP/hostname. URL&apos;e gerekiyorsa <code>/v1</code> ekle.
          </p>
        </div>
      )}
      {provider === "custom" && (
        <p className="-mt-2 text-xs text-zinc-500">
          Endpoint URL&apos;ini <code className="text-indigo-300">.env</code>&apos;deki{" "}
          <code className="text-indigo-300">CUSTOM_BASE_URL</code>&apos;e yaz (önerilen) ya da{" "}
          <Link href="/providers" className="text-indigo-400 hover:text-indigo-300">
            Sağlayıcılar
          </Link>{" "}
          sayfasından gir — OpenAI-uyumlu base_url + (gerekiyorsa) API anahtarı.
        </p>
      )}

      <Input
        label="Temperature"
        type="number"
        step="0.1"
        min="0"
        max="2"
        value={temperature}
        onChange={(e) => setTemperature(parseFloat(e.target.value))}
      />

      {/* Tool kategorileri */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium tracking-wide text-zinc-400">Araçlar — kategoriler</span>
        <div className="flex flex-col gap-2">
          {categories.map((cat) => {
            const Icon = CATEGORY_ICONS[cat.key] ?? Globe;

            // Dosya kategorisi → "Dosya sistemi" anahtarıyla yönetilir
            if (cat.managed_by_file_system) {
              return (
                <div
                  key={cat.key}
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
                        <Icon size={14} className="text-indigo-400" />
                        <span className="text-sm text-zinc-200">{cat.label}</span>
                        <span className="text-[11px] text-zinc-600">({cat.tools.length} araç)</span>
                      </div>
                      <p className="mt-0.5 text-xs text-zinc-500">
                        Açılırsa {cat.tools.map((t) => t.name).join(", ")} otomatik eklenir.
                        Veri kaybettirebilecek araçlar (sil/düzenle/klasör-sil) varsayılan
                        olarak onaydan geçer.
                      </p>
                    </div>
                  </label>
                </div>
              );
            }

            // Yakında (finance/operation)
            if (cat.coming_soon) {
              return (
                <div
                  key={cat.key}
                  className="flex items-center gap-2 rounded-lg border border-dashed border-zinc-800 px-3 py-2.5 opacity-60"
                >
                  <Icon size={14} className="text-zinc-600" />
                  <span className="text-sm text-zinc-400">{cat.label}</span>
                  <span className="ml-auto rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500">
                    yakında
                  </span>
                </div>
              );
            }

            // Seçilebilir kategori (web / self)
            const toolNames = cat.tools.map((t) => t.name);
            const allOn = toolNames.length > 0 && toolNames.every((n) => selected.has(n));
            return (
              <div key={cat.key} className="rounded-lg border border-zinc-800 px-3 py-2.5">
                <div className="mb-1.5 flex items-center gap-2">
                  <Icon size={14} className="text-indigo-400" />
                  <span className="text-sm font-medium text-zinc-200">{cat.label}</span>
                  <span className="text-[11px] text-zinc-600">{cat.note}</span>
                  <button
                    type="button"
                    onClick={() => setCategoryTools(toolNames, !allOn)}
                    className="ml-auto text-[11px] text-indigo-400 transition-colors hover:text-indigo-300"
                  >
                    {allOn ? "Tümünü kaldır" : "Tümünü seç"}
                  </button>
                </div>
                <div className="flex flex-col gap-1.5">
                  {cat.tools.map((tool) => {
                    const isSelected = selected.has(tool.name);
                    const isHitl = hitl.has(tool.name);
                    return (
                      <div
                        key={tool.name}
                        className={cn(
                          "rounded-md border px-3 py-2 transition-colors",
                          isSelected
                            ? "border-indigo-500/30 bg-indigo-500/5"
                            : "border-zinc-800/70 hover:border-zinc-700",
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
                            İnsan onayı gerektir (HITL)
                          </label>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <Button type="submit" size="lg" loading={submitting} className="mt-2">
        {submitLabel}
      </Button>
    </form>
  );
}
