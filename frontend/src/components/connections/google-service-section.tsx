"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Mail, Calendar, HardDrive, Check, X, AlertTriangle } from "lucide-react";
import { api, ApiError, type ServiceConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

const SERVICE_META = {
  gmail: {
    label: "Gmail",
    desc: "Agent senin adına e-posta okur, arar ve gönderir.",
    icon: Mail,
    iconClass: "text-red-400",
    iconBg: "bg-red-500/10",
    scopeKw: "gmail",
    tools: "gmail_read, gmail_search, gmail_send",
  },
  gcalendar: {
    label: "Google Takvim",
    desc: "Agent takvimindeki etkinlikleri listeler ve yeni etkinlik oluşturur.",
    icon: Calendar,
    iconClass: "text-blue-400",
    iconBg: "bg-blue-500/10",
    scopeKw: "calendar",
    tools: "calendar_list, calendar_create",
  },
  gdrive: {
    label: "Google Drive",
    desc: "Agent Drive'da dosya arar ve içeriklerini okur.",
    icon: HardDrive,
    iconClass: "text-green-400",
    iconBg: "bg-green-500/10",
    scopeKw: "drive",
    tools: "drive_search, drive_read",
  },
};

export type GoogleService = keyof typeof SERVICE_META;

export function GoogleServiceSection({ service }: { service: GoogleService }) {
  const params = useSearchParams();
  const [connections, setConnections] = useState<ServiceConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState(false);

  const meta = SERVICE_META[service];
  const Icon = meta.icon;

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
  const hasScope = !!(google?.scopes ?? []).some((s) => s.includes(meta.scopeKw));
  const connected = !!google;

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
    if (!window.confirm("Google bağlantısını tamamen kes? (Gmail, Takvim ve Drive erişimi kalkar)")) return;
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
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${meta.iconBg}`}>
              <Icon size={18} className={meta.iconClass} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-zinc-200">{meta.label}</p>
              {hasScope ? (
                <p className="flex items-center gap-1 text-xs text-green-400">
                  <Check size={12} /> {google?.account_email ?? "bağlı"} · yetkilendirildi
                </p>
              ) : connected ? (
                <p className="flex items-center gap-1 text-xs text-amber-400">
                  <AlertTriangle size={12} /> Bağlı ama {meta.label} izni yok — yeniden bağlan
                </p>
              ) : (
                <p className="text-xs text-zinc-500">Bağlı değil</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {connected && (
                <Button size="sm" variant="outline" onClick={disconnectGoogle}>
                  <X size={13} /> Kes
                </Button>
              )}
              <Button size="sm" onClick={connectGoogle} loading={connecting}>
                {hasScope ? "Yeniden bağlan" : "Bağlan"}
              </Button>
            </div>
          </div>

          {hasScope && (
            <div className="mt-3 border-t border-zinc-800/60 pt-3">
              <p className="text-[11px] text-zinc-600">
                Agent tool'ları: <span className="font-mono text-indigo-400">{meta.tools}</span>
              </p>
            </div>
          )}

          {connected && !hasScope && (
            <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2">
              <p className="text-[11px] text-amber-400/80">
                Google hesabın bağlı ama {meta.label} için izin verilmemiş. "Bağlan" butonuna tıkla ve onay ekranında bu servisi de seç.
              </p>
            </div>
          )}
        </div>
      )}

      <p className="mt-3 text-[11px] text-zinc-600">
        OAuth ile bağlanırsın — agent oluştururken <span className="text-zinc-400">{meta.tools.split(",")[0].trim()}</span> araçlarını ekleyebilirsin.
      </p>
    </div>
  );
}
