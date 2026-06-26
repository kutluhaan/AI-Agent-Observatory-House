"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api, ApiError, type TestSuite, type Agent } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { GuideDrawer } from "@/components/test-suites/guide-panel";

const EXAMPLE_YAML = `name: research-suite
description: Checks for a file-system research agent
agent_id: "<agent-uuid>"
cases:
  - name: researches-and-saves
    input: "Research burotime and save findings to research/burotime.md"
    assertions:
      # Çıktı (deterministik)
      - type: response_contains
        value: "burotime"
      - type: response_not_contains
        value: "I cannot"
      # - type: response_regex
      #   value: "\\\\bsource(s)?\\\\b"
      # Trajectory / tool kullanımı
      - type: tools_used
        value: ["web_search", "write_file"]
      - type: tool_sequence            # bu sırayla (aralarında başka adım olabilir)
        value: ["web_search", "write_file"]
      - type: tool_called_with_args
        value: { name: "write_file", args: { path: "research/burotime.md" } }
      - type: no_tool_errors
        value: true
      # Güvenlik (deterministik)
      - type: no_pii            # çıktıda email/uzun numara sızıntısı yok
        value: true
      - type: not_refused       # geçerli isteği reddetmedi
        value: true
      # Operasyonel bütçeler
      - type: steps_under
        value: 8
      - type: tokens_under
        value: 40000
      - type: cost_under
        value: 0.05
      - type: latency_under
        value: 60000
    # Tutarlılık (opsiyonel): 3 kez çalıştır, en az 2/3 geçerse "passed"
    repeat: 3
    min_pass_rate: 0.66
    # LLM-as-judge (opsiyonel — token harcar, sadece tanımlarsan çalışır)
    judges:
      - type: task_completion        # hedefe ulaştı mı? (skor 0–1, eşik 0.7)
      - type: step_efficiency
        threshold: 0.6
      - type: safety                 # toksik/zararlı/PII içeriği yok mu
        threshold: 0.9
      - type: rubric
        criteria: "Cevap Türkçe olmalı ve en az bir kaynak belirtmeli."
`;

export default function NewTestSuitePage() {
  const router = useRouter();
  const [mode, setMode] = useState<"yaml" | "dataset">("yaml");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [configYaml, setConfigYaml] = useState(EXAMPLE_YAML);
  // B2 — dataset modu
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [format, setFormat] = useState<"csv" | "jsonl">("csv");
  const [assertion, setAssertion] = useState<"contains" | "equals" | "regex">("contains");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Agent[]>("/agents").then(setAgents).catch(() => {});
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      let suite: TestSuite;
      if (mode === "dataset") {
        suite = await api.post<TestSuite>("/test-suites/from-dataset", {
          name, description: description || null, agent_id: agentId, format, content, assertion,
        });
      } else {
        suite = await api.post<TestSuite>("/test-suites", {
          name, description: description || null, config_yaml: configYaml,
        });
      }
      router.replace(`/test-suites/${suite.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create suite.");
      setSubmitting(false);
    }
  }

  const datasetValid = name.trim() && agentId && content.trim();
  const yamlValid = name.trim() && configYaml.trim();

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <Link
        href="/test-suites"
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Test suites
      </Link>

      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">Yeni test suite</h1>
        <GuideDrawer />
      </div>

      {/* Mod seçimi: YAML | Dataset */}
      <div className="mb-5 inline-flex items-center rounded-lg border border-zinc-800 bg-zinc-950/50 p-0.5 text-xs">
        {(["yaml", "dataset"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={cn(
              "rounded-md px-3 py-1.5 font-medium transition-colors",
              mode === m ? "bg-indigo-500/20 text-indigo-200" : "text-zinc-500 hover:text-zinc-300",
            )}
          >
            {m === "yaml" ? "YAML" : "Dataset (CSV/JSONL)"}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <Alert variant="error">{error}</Alert>}

        <Input label="Ad" value={name} onChange={(e) => setName(e.target.value)} placeholder="Müşteri SSS testi" required />
        <Input label="Açıklama" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Opsiyonel" />

        {mode === "yaml" ? (
          <Textarea
            label="Configuration (YAML)"
            value={configYaml}
            onChange={(e) => setConfigYaml(e.target.value)}
            rows={14}
            className="font-mono text-xs"
            hint="agent_id'yi gerçek agent'a ayarla. Assertion'lar: response_contains/not_contains/equals/regex · tool_*/no_tool_errors · no_pii/not_refused · steps/tokens/cost/latency_under. judges: task_completion/answer_correctness/rubric/.../output_quality. Senaryo: case'te 'input' yerine 'steps: [{input, assertions}]'."
          />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              <Dropdown
                label="Agent"
                value={agentId}
                options={[{ value: "", label: "— seç —" }, ...agents.map((a) => ({ value: a.id, label: a.name }))]}
                onChange={setAgentId}
              />
              <Dropdown label="Format" value={format} options={[{ value: "csv", label: "CSV" }, { value: "jsonl", label: "JSONL" }]} onChange={(v) => setFormat(v as "csv" | "jsonl")} />
              <Dropdown label="Eşleşme" value={assertion} options={[{ value: "contains", label: "İçerir" }, { value: "equals", label: "Eşittir" }, { value: "regex", label: "Regex" }]} onChange={(v) => setAssertion(v as "contains" | "equals" | "regex")} />
            </div>
            <Textarea
              label={format === "csv" ? "CSV (başlık: input,expected)" : "JSONL (her satır {\"input\":..., \"expected\":...})"}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={12}
              className="font-mono text-xs"
              placeholder={format === "csv"
                ? "input,expected\nİstanbul hava durumu nedir?,derece\nNotion nedir?,not"
                : '{"input": "İstanbul hava durumu?", "expected": "derece"}\n{"input": "Notion nedir?", "expected": "not"}'}
            />
            <p className="-mt-2 text-[11px] text-zinc-600">
              Her satır bir test case olur. <span className="text-zinc-400">expected</span> doluysa
              seçtiğin eşleşme tipinde bir assertion eklenir; boşsa case sadece çalışır (judge ile değerlendirebilirsin).
              Oluşturduktan sonra YAML olarak düzenlenebilir.
            </p>
          </>
        )}

        <Button type="submit" size="lg" loading={submitting} disabled={mode === "dataset" ? !datasetValid : !yamlValid} className="mt-2">
          Suite oluştur
        </Button>
      </form>
    </div>
  );
}
