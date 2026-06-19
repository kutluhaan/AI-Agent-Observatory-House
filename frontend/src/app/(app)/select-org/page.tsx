"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Plus, Building2 } from "lucide-react";
import { Logo } from "@/components/logo";
import { Alert } from "@/components/ui/alert";
import { api, ApiError, type Organization } from "@/lib/api";
import { useAuth } from "@/contexts/auth";
import { cn } from "@/lib/utils";

export default function SelectOrgPage() {
  const router = useRouter();
  const { user, refresh } = useAuth();

  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);
  const [error, setError] = useState("");

  // Org listesi /auth/me'den gelir (user.organizations) — ayrı bir liste endpoint'i yok.
  useEffect(() => {
    if (user) {
      setOrgs(user.organizations);
      setLoading(false);
    }
  }, [user]);

  async function handleSelect(orgId: string) {
    if (switching) return;
    setSwitching(orgId);
    setError("");
    try {
      await api.post("/auth/switch-org", { org_id: orgId });
      await refresh();
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not switch workspace.",
      );
      setSwitching(null);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-[400px] animate-slide-up">
        <div className="mb-10 flex justify-center">
          <Logo showWordmark wordmarkSize="md" />
        </div>

        <div className="mb-7">
          <h1 className="text-xl font-semibold text-zinc-100">
            Switch workspace
          </h1>
          <p className="mt-1.5 text-sm text-zinc-500">
            Select a workspace to continue.
          </p>
        </div>

        {error && <Alert variant="error" className="mb-4">{error}</Alert>}

        {loading ? (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {orgs.map((org) => {
              const isCurrent = org.id === user?.org_id;
              const isLoading = switching === org.id;

              return (
                <button
                  key={org.id}
                  onClick={() => handleSelect(org.id)}
                  disabled={!!switching}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl border px-4 py-3.5 text-left",
                    "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60",
                    isCurrent
                      ? "border-indigo-500/30 bg-indigo-500/8"
                      : "border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/60",
                  )}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
                    <Building2 size={15} className="text-zinc-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-200">
                      {org.name}
                    </p>
                    <p className="text-xs text-zinc-600">
                      {org.slug} · {org.role}
                    </p>
                  </div>
                  <div className="shrink-0">
                    {isLoading ? (
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
                    ) : isCurrent ? (
                      <Check size={15} className="text-indigo-400" />
                    ) : null}
                  </div>
                </button>
              );
            })}

            <button
              onClick={() => router.push("/create-org")}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border border-dashed border-zinc-800",
                "px-4 py-3.5 text-left transition-colors hover:border-zinc-700 hover:bg-zinc-900/40",
              )}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-dashed border-zinc-700">
                <Plus size={15} className="text-zinc-500" />
              </div>
              <span className="text-sm text-zinc-500">Create new workspace</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
