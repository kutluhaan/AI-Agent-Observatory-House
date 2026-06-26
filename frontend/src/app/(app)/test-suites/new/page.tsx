"use client";

import { useEffect, useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Bot, Users, Check } from "lucide-react";
import { api, ApiError, type TestSuite, type Agent, type Team } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import { GuideDrawer } from "@/components/test-suites/guide-panel";

const YAML_TEMPLATE = (kind: "agent" | "team", id: string, displayName: string) => {
  const idLine = kind === "agent"
    ? `agent_id: "${id || "<agent seç →>"}"`
    : `team_id: "${id || "<ekip seç →>"}"`;
  const nameNote = displayName ? `  # ${displayName}` : "";
  return `name: suite-adi
description: "açıklama"
${idLine}${nameNote}

cases:
  - name: test-adi
    input: "test girdisi"
    assertions:
      - type: not_refused
        value: true
      - type: steps_under
        value: 10
`;
};

function injectId(yaml: string, kind: "agent" | "team", id: string, displayName: string): string {
  const nameNote = displayName ? `  # ${displayName}` : "";
  const newLine = kind === "agent"
    ? `agent_id: "${id}"${nameNote}`
    : `team_id: "${id}"${nameNote}`;

  // Replace existing agent_id or team_id line
  if (/^(agent_id|team_id):\s*/m.test(yaml)) {
    return yaml.replace(/^(agent_id|team_id):.*$/m, newLine);
  }
  // Insert after first line (name: ...)
  const lines = yaml.split("\n");
  const nameIdx = lines.findIndex((l) => /^name:/.test(l));
  if (nameIdx >= 0) {
    lines.splice(nameIdx + 1, 0, newLine);
    return lines.join("\n");
  }
  return `${newLine}\n${yaml}`;
}

export default function NewTestSuitePage() {
  const router = useRouter();
  const [mode, setMode] = useState<"yaml" | "dataset">("yaml");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Selector panel
  const [selectorKind, setSelectorKind] = useState<"agent" | "team">("agent");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [loadingList, setLoadingList] = useState(true);

  // YAML mode
  const [configYaml, setConfigYaml] = useState(YAML_TEMPLATE("agent", "", ""));

  // Dataset mode
  const [agentId, setAgentId] = useState("");
  const [format, setFormat] = useState<"csv" | "jsonl">("csv");
  const [assertion, setAssertion] = useState<"contains" | "equals" | "regex">("contains");
  const [content, setContent] = useState("");

  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setLoadingList(true);
    Promise.all([
      api.get<Agent[]>("/agents").catch(() => [] as Agent[]),
      api.get<Team[]>("/teams").catch(() => [] as Team[]),
    ]).then(([a, t]) => {
      setAgents(a);
      setTeams(t);
    }).finally(() => setLoadingList(false));
  }, []);

  const handleSelect = useCallback((kind: "agent" | "team", id: string, label: string) => {
    setSelectedId(id);
    setSelectedName(label);
    setConfigYaml((prev) => injectId(prev, kind, id, label));
    if (kind === "agent") setAgentId(id);
  }, []);

  function handleSelectorKindChange(kind: "agent" | "team") {
    setSelectorKind(kind);
    setSelectedId("");
    setSelectedName("");
    // Reset yaml to new template for this kind
    setConfigYaml(YAML_TEMPLATE(kind, "", ""));
  }

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
  const list = selectorKind === "agent" ? agents : teams;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-10">
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

      <div className="flex gap-6 items-start">

        {/* ── Sol panel: Agent / Ekip seçici ─────────────────── */}
        <aside className="w-52 shrink-0 flex flex-col gap-3 sticky top-6">
          {/* Toggle */}
          <div className="inline-flex w-full rounded-lg border border-zinc-800 bg-zinc-950/50 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => handleSelectorKindChange("agent")}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 font-medium transition-colors",
                selectorKind === "agent"
                  ? "bg-indigo-500/20 text-indigo-200"
                  : "text-zinc-500 hover:text-zinc-300",
              )}
            >
              <Bot size={12} />
              Agent
            </button>
            <button
              type="button"
              onClick={() => handleSelectorKindChange("team")}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 font-medium transition-colors",
                selectorKind === "team"
                  ? "bg-violet-500/20 text-violet-200"
                  : "text-zinc-500 hover:text-zinc-300",
              )}
            >
              <Users size={12} />
              Ekip
            </button>
          </div>

          {/* Liste */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 overflow-hidden">
            <div className="max-h-[420px] overflow-y-auto">
              {loadingList ? (
                <div className="flex justify-center py-8">
                  <Spinner className="h-4 w-4" />
                </div>
              ) : list.length === 0 ? (
                <p className="py-8 text-center text-[11px] text-zinc-600">
                  {selectorKind === "agent" ? "Agent bulunamadı" : "Ekip bulunamadı"}
                </p>
              ) : (
                list.map((item, i) => {
                  const itemId = item.id;
                  const itemName = item.name;
                  const isSelected = selectedId === itemId;
                  const accent = selectorKind === "agent" ? "indigo" : "violet";
                  return (
                    <button
                      key={itemId}
                      type="button"
                      onClick={() => handleSelect(selectorKind, itemId, itemName)}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors",
                        i > 0 && "border-t border-zinc-800/50",
                        isSelected
                          ? accent === "indigo"
                            ? "bg-indigo-500/10 text-indigo-200"
                            : "bg-violet-500/10 text-violet-200"
                          : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200",
                      )}
                    >
                      <span className="flex-1 truncate font-medium">{itemName}</span>
                      {isSelected && (
                        <Check size={12} className={accent === "indigo" ? "text-indigo-400 shrink-0" : "text-violet-400 shrink-0"} />
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Seçili UUID göster */}
          {selectedId && (
            <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/60 px-2.5 py-2">
              <p className="text-[10px] text-zinc-600 mb-0.5">Seçilen UUID</p>
              <p className="font-mono text-[10px] text-zinc-400 break-all">{selectedId}</p>
            </div>
          )}
        </aside>

        {/* ── Sağ: Form ──────────────────────────────────────── */}
        <div className="flex-1 min-w-0">
          {/* Mod seçimi */}
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
                rows={16}
                className="font-mono text-xs"
                hint={
                  selectedId
                    ? `${selectorKind === "agent" ? "Agent" : "Ekip"}: ${selectedName} — UUID YAML'a eklendi.`
                    : `Soldan bir ${selectorKind === "agent" ? "agent" : "ekip"} seçince UUID otomatik girer.`
                }
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
                  seçtiğin eşleşme tipinde bir assertion eklenir; boşsa case sadece çalışır.
                  Oluşturduktan sonra YAML olarak düzenlenebilir.
                </p>
              </>
            )}

            <Button type="submit" size="lg" loading={submitting} disabled={mode === "dataset" ? !datasetValid : !yamlValid} className="mt-2">
              Suite oluştur
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
