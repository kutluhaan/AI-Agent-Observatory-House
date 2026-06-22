"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Mail, Plug, Check, X } from "lucide-react";
import { api, ApiError, type ServiceConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-20"><Spinner className="h-5 w-5" /></div>}>
      <ConnectionsInner />
    </Suspense>
  );
}

function ConnectionsInner() {
  const params = useSearchParams();
  const [connections, setConnections] = useState<ServiceConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState(false);

  const load = useCallback(() => {
    api.get<ServiceConnection[]>("/connections").then(setConnections).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  // Callback'ten dönüş bildirimi
  const googleStatus = params.get("google");
  const banner =
    googleStatus === "connected" ? { v: "success" as const, t: "Gmail bağlandı ✓" }
    : googleStatus === "expired" ? { v: "error" as const, t: "Oturum/state süresi doldu, tekrar dene." }
    : googleStatus === "error" ? { v: "error" as const, t: "Bağlantı başarısız. Google Cloud ayarlarını kontrol et." }
    : null;

  const google = connections.find((c) => c.provider === "google");

  async function connectGoogle() {
    setConnecting(true);
    setError("");
    try {
      const { authorize_url } = await api.post<{ authorize_url: string }>("/connections/google/authorize", {});
      window.location.href = authorize_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Başlatılamadı.");
      setConnecting(false);
    }
  }

  async function disconnectGoogle() {
    if (!window.confirm("Gmail bağlantısını kes?")) return;
    try {
      await api.delete("/connections/google");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kesilemedi.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <div className="mb-2 flex items-center gap-2">
        <Plug size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Bağlantılar</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Kendi hesaplarını bağla; agent&apos;lar senin adına bu servisleri kullanabilsin.
      </p>

      {banner && <Alert variant={banner.v} className="mb-4">{banner.t}</Alert>}
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="h-5 w-5" /></div>
      ) : (
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
              <Mail size={18} className="text-red-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-zinc-200">Gmail</p>
              {google ? (
                <p className="flex items-center gap-1 text-xs text-green-400">
                  <Check size={12} /> {google.account_email ?? "bağlı"}
                </p>
              ) : (
                <p className="text-xs text-zinc-500">Bağlı değil — oku/ara/gönder için bağla</p>
              )}
            </div>
            {google ? (
              <Button size="sm" variant="outline" onClick={disconnectGoogle}>
                <X size={13} /> Bağlantıyı kes
              </Button>
            ) : (
              <Button size="sm" onClick={connectGoogle} loading={connecting}>
                Google ile bağlan
              </Button>
            )}
          </div>
          {google && (
            <p className="mt-3 border-t border-zinc-800/60 pt-3 text-[11px] text-zinc-600">
              İzinler: {google.scopes.filter((s) => s.includes("gmail")).join(", ") || "—"}
            </p>
          )}
        </div>
      )}

      <p className="mt-4 text-[11px] text-zinc-600">
        Agent oluştururken <span className="text-zinc-400">E-posta (Gmail)</span> kategorisinden
        gmail araçlarını seç. Araçlar senin bağladığın hesapla çalışır.
      </p>
    </div>
  );
}
