"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, X, AlertTriangle } from "lucide-react";
import { api, ApiError, type ServiceConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

// Source: Simple Icons (simpleicons.org)
function GmailIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
    </svg>
  );
}

function GoogleDriveIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12.01 1.485c-2.082 0-3.754.02-3.743.047.01.02 1.708 3.001 3.774 6.62l3.76 6.574h3.76c2.081 0 3.753-.02 3.742-.047-.005-.02-1.708-3.001-3.775-6.62l-3.76-6.574zm-4.76 1.73a789.828 789.861 0 0 0-3.63 6.319L0 15.868l1.89 3.298 1.885 3.297 3.62-6.335 3.618-6.33-1.88-3.287C8.1 4.704 7.255 3.22 7.25 3.214zm2.259 12.653-.203.348c-.114.198-.96 1.672-1.88 3.287a423.93 423.948 0 0 1-1.698 2.97c-.01.026 3.24.042 7.222.042h7.244l1.796-3.157c.992-1.734 1.85-3.23 1.906-3.323l.104-.167h-7.249z"/>
    </svg>
  );
}

function GoogleCalendarIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.316 5.684H24v12.632h-5.684V5.684zM5.684 24h12.632v-5.684H5.684V24zM18.316 5.684V0H1.895A1.894 1.894 0 0 0 0 1.895v16.421h5.684V5.684h12.632zm-7.207 6.25v-.065c.272-.144.5-.349.687-.617s.279-.595.279-.982c0-.379-.099-.72-.3-1.025a2.05 2.05 0 0 0-.832-.714 2.703 2.703 0 0 0-1.197-.257c-.6 0-1.094.156-1.481.467-.386.311-.65.671-.793 1.078l1.085.452c.086-.249.224-.461.413-.633.189-.172.445-.257.767-.257.33 0 .602.088.816.264a.86.86 0 0 1 .322.703c0 .33-.12.589-.36.778-.24.19-.535.284-.886.284h-.567v1.085h.633c.407 0 .748.109 1.02.327.272.218.407.499.407.843 0 .336-.129.614-.387.832s-.565.327-.924.327c-.351 0-.651-.103-.897-.311-.248-.208-.422-.502-.521-.881l-1.096.452c.178.616.505 1.082.977 1.401.472.319.984.478 1.538.477a2.84 2.84 0 0 0 1.293-.291c.382-.193.684-.458.902-.794.218-.336.327-.72.327-1.149 0-.429-.115-.797-.344-1.105a2.067 2.067 0 0 0-.881-.689zm2.093-1.931.602.913L15 10.045v5.744h1.187V8.446h-.827l-2.158 1.557zM22.105 0h-3.289v5.184H24V1.895A1.894 1.894 0 0 0 22.105 0zm-3.289 23.5 4.684-4.684h-4.684V23.5zM0 22.105C0 23.152.848 24 1.895 24h3.289v-5.184H0v3.289z"/>
    </svg>
  );
}

const SERVICE_META = {
  gmail: {
    label: "Gmail",
    desc: "Agent senin adına e-posta okur, arar ve gönderir.",
    Icon: GmailIcon,
    iconClass: "text-red-400",
    iconBg: "bg-red-500/10",
    scopeKw: "gmail",
    tools: "gmail_read, gmail_search, gmail_send",
  },
  gcalendar: {
    label: "Google Takvim",
    desc: "Agent takvimindeki etkinlikleri listeler ve yeni etkinlik oluşturur.",
    Icon: GoogleCalendarIcon,
    iconClass: "text-blue-400",
    iconBg: "bg-blue-500/10",
    scopeKw: "calendar",
    tools: "calendar_list, calendar_create",
  },
  gdrive: {
    label: "Google Drive",
    desc: "Agent Drive'da dosya arar ve içeriklerini okur.",
    Icon: GoogleDriveIcon,
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
  const { Icon } = meta;

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
              <Icon size={18} />
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
