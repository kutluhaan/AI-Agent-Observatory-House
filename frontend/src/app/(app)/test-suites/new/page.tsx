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

const EXAMPLE_YAML = `name: echo-suite
description: Basic checks for the echo agent
agent_id: "<agent-uuid>"
cases:
  - name: greets-back
    input: "Hello"
    assertions:
      - type: response_contains
        value: "hello"
      - type: latency_under
        value: 10000
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
          hint="Set agent_id to a real agent. Assertions: response_contains, tool_called, latency_under."
          required
        />

        <Button type="submit" size="lg" loading={submitting} className="mt-2">
          Create suite
        </Button>
      </form>
    </div>
  );
}
