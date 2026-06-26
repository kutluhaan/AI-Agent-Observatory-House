"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Mail, Check, X, Calendar, HardDrive } from "lucide-react";
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
  const hasScope = (kw: string) => (google?.scopes ?? []).some((s) => s.includes(kw));
  const SERVICES = [
    { key: "gmail", label: "Gmail", desc: "E-posta oku & gönder", icon: Mail, ok: hasScope("gmail") },
    { key: "calendar", label: "Google Takvim", desc: "Etkinlik listele & oluştur", icon: Calendar, ok: hasScope("calendar") },
    { key: "drive", label: "Google Drive", desc: "Dosya ara & oku", icon: HardDrive, ok: hasScope("drive") },
  ];
  const missingSome = !!google && SERVICES.some((s) => !s.ok);

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
          {/* Hesap başlığı */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
              <Mail size={18} className="text-red-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-zinc-200">Google</p>
              {google ? (
                <p className="flex items-center gap-1 text-xs text-green-400">
                  <Check size={12} /> {google.account_email ?? "bağlı"}
                </p>
              ) : (
                <p className="text-xs text-zinc-500">Bağlı değil — bağlandığında her servis ayrı yetkilendirilir</p>
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

          {/* Servisler — granted scope'lara göre AYRI ayrı gerçek durum */}
          <div className="mt-3 flex flex-col gap-2 border-t border-zinc-800/60 pt-3">
            {SERVICES.map((s) => (
              <div key={s.key} className="flex items-center gap-2.5">
                <s.icon size={15} className={s.ok ? "text-zinc-300" : "text-zinc-600"} />
                <div className="flex-1">
                  <p className={s.ok ? "text-xs text-zinc-200" : "text-xs text-zinc-500"}>{s.label}</p>
                  <p className="text-[10px] text-zinc-600">{s.desc}</p>
                </div>
                {s.ok ? (
                  <span className="flex items-center gap-1 text-[11px] text-green-400"><Check size={12} />yetkili</span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] text-zinc-600"><X size={12} />izin yok</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {missingSome && (
        <p className="mt-4 text-[11px] text-amber-400/80">
          Bazı servislerin izni yok. Takvim/Drive&apos;ı kullanmak için bağlantıyı kesip yeniden bağlan — onay ekranında tüm izinleri ver.
        </p>
      )}
      <p className="mt-2 text-[11px] text-zinc-600">
        Agent oluştururken <span className="text-zinc-400">E-posta (Gmail)</span>, <span className="text-zinc-400">Takvim</span> ve <span className="text-zinc-400">Drive</span> araçlarını yalnız yetkili servisler için seç.
      </p>
    </div>
  );
}
