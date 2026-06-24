"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Mail, Check, X } from "lucide-react";
import { api, ApiError, type ServiceConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

/** Google (Gmail + Takvim/Drive) OAuth bağlantısı. Bağlantılar hub'ında "Google" kategorisi. */
export function GoogleSection() {
  const params = useSearchParams();
  const [connections, setConnections] = useState<ServiceConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState(false);

  const load = useCallback(() => {
    api.get<ServiceConnection[]>("/connections").then(setConnections).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const googleStatus = params.get("google");
  const banner =
    googleStatus === "connected" ? { v: "success" as const, t: "Google bağlandı ✓" }
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
    if (!window.confirm("Google bağlantısını kes?")) return;
    try {
      await api.delete("/connections/google");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kesilemedi.");
    }
  }

  return (
    <div>
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
              <p className="text-sm font-medium text-zinc-200">Google (Gmail · Takvim · Drive)</p>
              {google ? (
                <p className="flex items-center gap-1 text-xs text-green-400">
                  <Check size={12} /> {google.account_email ?? "bağlı"}
                </p>
              ) : (
                <p className="text-xs text-zinc-500">Bağlı değil — Gmail/Takvim/Drive araçları için bağla</p>
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
              İzinler: {google.scopes.map((s) => s.split("/").pop()).filter(Boolean).join(", ") || "—"}
            </p>
          )}
        </div>
      )}
      <p className="mt-4 text-[11px] text-zinc-600">
        Yeni izin (Takvim/Drive) eklendiyse bağlantıyı kesip yeniden bağla. Agent oluştururken
        <span className="text-zinc-400"> E-posta (Gmail)</span> ve <span className="text-zinc-400">Takvim & Drive</span> kategorilerinden araçları seç.
      </p>
    </div>
  );
}
