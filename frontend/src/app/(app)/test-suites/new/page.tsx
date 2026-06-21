"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api, ApiError, type TestSuite } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";

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
      # Operasyonel bütçeler
      - type: steps_under
        value: 8
      - type: tokens_under
        value: 40000
      - type: cost_under
        value: 0.05
      - type: latency_under
        value: 60000
`;

export default function NewTestSuitePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [configYaml, setConfigYaml] = useState(EXAMPLE_YAML);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const suite = await api.post<TestSuite>("/test-suites", {
        name,
        description: description || null,
        config_yaml: configYaml,
      });
      router.replace(`/test-suites/${suite.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create suite.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <Link
        href="/test-suites"
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Test suites
      </Link>

      <h1 className="mb-6 text-xl font-semibold text-zinc-100">New test suite</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <Alert variant="error">{error}</Alert>}

        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Echo agent regression"
          required
        />
        <Input
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional"
        />
        <Textarea
          label="Configuration (YAML)"
          value={configYaml}
          onChange={(e) => setConfigYaml(e.target.value)}
          rows={14}
          className="font-mono text-xs"
          hint="agent_id'yi gerçek bir agent'a ayarla. Assertion'lar — çıktı: response_contains/not_contains/equals/regex · tool: tool_called/tool_called_with_args/tool_sequence/tools_used/no_tool_errors · bütçe: steps_under/tokens_under/cost_under/latency_under/finish_reason_is."
          required
        />

        <Button type="submit" size="lg" loading={submitting} className="mt-2">
          Create suite
        </Button>
      </form>
    </div>
  );
}
