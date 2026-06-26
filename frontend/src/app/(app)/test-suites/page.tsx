"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TestTube2, Plus, ChevronRight, Trash2 } from "lucide-react";
import { api, type TestSuite } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function TestSuitesPage() {
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TestSuite[]>("/test-suites")
      .then(setSuites)
      .catch(() => setError("Failed to load test suites."))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(e: React.MouseEvent, id: string, name: string) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`"${name}" suite'ini silmek istediğine emin misin?`)) return;
    setDeleting(id);
    try {
      await api.delete(`/test-suites/${id}`);
      setSuites((prev) => prev.filter((s) => s.id !== id));
    } catch {
      setError("Silinemedi.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Test suites</h1>
          <p className="mt-1 text-sm text-zinc-500">
            YAML senaryolarını agent&apos;larına karşı çalıştır.
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
          <p className="text-sm text-zinc-400">Henüz test suite yok.</p>
          <p className="mt-1 text-xs text-zinc-600">
            YAML suite oluşturarak agent testine başla.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {suites.map((s, i) => (
            <div
              key={s.id}
              className={
                "group flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-zinc-900/60 " +
                (i > 0 ? "border-t border-zinc-800/60" : "")
              }
            >
              <Link href={`/test-suites/${s.id}`} className="flex flex-1 items-center gap-4 min-w-0">
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
              <button
                onClick={(e) => handleDelete(e, s.id, s.name)}
                disabled={deleting === s.id}
                className="shrink-0 rounded-md p-1.5 text-zinc-700 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100 disabled:opacity-50"
                title="Sil"
              >
                {deleting === s.id ? (
                  <Spinner className="h-3.5 w-3.5" />
                ) : (
                  <Trash2 size={14} />
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
