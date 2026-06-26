"use client";

import { useCallback, useEffect, useState } from "react";
import { Server, CheckCircle2, Trash2, Activity } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ProviderEntry {
  provider: string;
  is_configured: boolean;
  masked_key: string | null;
  base_url: string | null;
  updated_at: string | null;
}

const LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Google Gemini",
  ollama: "Ollama (yerel)",
  custom: "Custom (OpenAI-uyumlu)",
};

const DESCRIPTIONS: Record<string, string> = {
  openai: "GPT-4o, GPT-4o mini, o1, o3-mini",
  anthropic: "Claude Opus, Sonnet, Haiku",
  gemini: "Gemini 2.5 Pro, Flash, Nano",
  ollama: "Llama, Mistral, Qwen — local GPU/CPU",
  custom: "vLLM, LM Studio, LocalAI, Azure OpenAI — herhangi OpenAI-uyumlu endpoint",
};

// base_url alanı olanlar
const HAS_BASE_URL = new Set(["ollama", "custom"]);
// api_key zorunlu olanlar (ollama yok, custom opsiyonel)
const KEY_REQUIRED = new Set(["openai", "anthropic", "gemini"]);

const ORDER = ["custom", "openai", "anthropic", "gemini", "ollama"];

export default function ProvidersPage() {
  const [items, setItems] = useState<ProviderEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api
      .get<ProviderEntry[]>("/providers")
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(), [load]);

  const ordered = [...items].sort(
    (a, b) => ORDER.indexOf(a.provider) - ORDER.indexOf(b.provider),
  );

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-xl font-semibold text-zinc-100">
          <Server size={18} className="text-indigo-400" />
          Model sağlayıcıları
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Org&apos;a özel API anahtarları ve self-hosted (OpenAI-uyumlu) endpoint&apos;ler.
          Yapılandırılmayan sağlayıcılar platform anahtarına düşer.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {ordered.map((p) => (
            <ProviderCard key={p.provider} entry={p} onChange={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProviderCard({
  entry,
  onChange,
}: {
  entry: ProviderEntry;
  onChange: () => void;
}) {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(entry.base_url ?? "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const hasBaseUrl = HAS_BASE_URL.has(entry.provider);
  const keyRequired = KEY_REQUIRED.has(entry.provider);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const body: Record<string, string> = { provider: entry.provider };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      if (hasBaseUrl && baseUrl.trim()) body.base_url = baseUrl.trim();
      await api.post("/providers", body);
      setApiKey("");
      setMsg({ kind: "ok", text: "Kaydedildi." });
      onChange();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? err.message : "Kaydedilemedi." });
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.get<{ healthy: boolean }>(`/providers/${entry.provider}/health`);
      setMsg(
        r.healthy
          ? { kind: "ok", text: "Bağlantı sağlıklı ✓" }
          : { kind: "err", text: "Endpoint yanıt verdi ama sağlıksız." },
      );
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? err.message : "Bağlantı testi başarısız." });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`${LABELS[entry.provider]} yapılandırmasını sil?`)) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.delete(`/providers/${entry.provider}`);
      setBaseUrl("");
      onChange();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? err.message : "Silinemedi." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-4",
        entry.provider === "custom"
          ? "border-indigo-500/30 bg-indigo-500/5"
          : "border-zinc-800/80 bg-zinc-900/40",
      )}
    >
      <div className="mb-3 flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-zinc-200">{LABELS[entry.provider] ?? entry.provider}</span>
            {entry.is_configured ? (
              <Badge variant="green">
                <CheckCircle2 size={10} />
                yapılandırıldı
              </Badge>
            ) : (
              <Badge variant="zinc">yapılandırılmadı</Badge>
            )}
          </div>
          <p className="mt-0.5 text-[11px] text-zinc-600">{DESCRIPTIONS[entry.provider]}</p>
          {entry.base_url && (
            <p className="mt-0.5 truncate font-mono text-[11px] text-zinc-700">{entry.base_url}</p>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {hasBaseUrl && (
          <Input
            label={`Base URL${entry.provider === "custom" ? " (OpenAI-uyumlu, ör. http://gpu:8000/v1)" : ""}`}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={entry.provider === "custom" ? "http://sunucu:8000/v1" : "http://localhost:11434"}
          />
        )}
        <Input
          label={`API anahtarı${keyRequired ? "" : " (opsiyonel)"}`}
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={entry.masked_key ?? (keyRequired ? "sk-..." : "gerekmiyorsa boş bırak")}
        />
      </div>

      {msg && (
        <Alert variant={msg.kind === "ok" ? "success" : "error"} className="mt-3">
          {msg.text}
        </Alert>
      )}

      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" onClick={save} loading={busy}>
          Kaydet
        </Button>
        {entry.is_configured && (
          <>
            <Button size="sm" variant="outline" onClick={test} disabled={busy}>
              <Activity size={13} />
              Test et
            </Button>
            <Button size="sm" variant="ghost" onClick={remove} disabled={busy}>
              <Trash2 size={13} />
              Sil
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
