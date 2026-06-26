"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TestTube2, Plus, ChevronRight } from "lucide-react";
import { api, type TestSuite } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function TestSuitesPage() {
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<TestSuite[]>("/test-suites")
      .then(setSuites)
      .catch(() => setError("Failed to load test suites."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Test suites</h1>
          <p className="mt-1 text-sm text-zinc-500">
            YAML senaryolarını agent'larına karşı çalıştır.
          </p>
        </div>
        <Link href="/test-suites/new">
          <Button size="sm">
            <Plus size={14} />
            Yeni suite
          </Button>
        </Link>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : suites.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <TestTube2 size={28} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">No test suites yet.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Create a YAML suite to start testing agents.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {suites.map((s, i) => (
            <Link
              key={s.id}
              href={`/test-suites/${s.id}`}
              className={
                "flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-zinc-900/60 " +
                (i > 0 ? "border-t border-zinc-800/60" : "")
              }
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10">
                <TestTube2 size={15} className="text-indigo-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-zinc-200">{s.name}</p>
                {s.description && (
                  <p className="truncate text-xs text-zinc-600">{s.description}</p>
                )}
              </div>
              <ChevronRight size={14} className="shrink-0 text-zinc-700" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
