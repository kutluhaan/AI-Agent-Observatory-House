"use client";

import { useEffect, useState } from "react";
import { Bell, Send, Activity, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { api, type AppNotification } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "şimdi";
  if (m < 60) return `${m} dk önce`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} sa önce`;
  return new Date(iso).toLocaleString();
}

export default function NotificationsPage() {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<AppNotification[]>("/notifications").then(setItems).catch(() => {}).finally(() => setLoading(false));
    // sayfa açılınca okundu işaretle (badge sıfırlanır)
    api.post("/notifications/read-all").catch(() => {});
  }, []);

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <div className="mb-2 flex items-center gap-2">
        <Bell size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Bildirimler</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Agent&apos;ların gönderdiği bildirimler ve sistem olayları (ekip çalıştırması bitti/hata).
        Kanal eklemek için <span className="text-zinc-300">Bağlantılar → Bildirimler</span>.
      </p>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="h-5 w-5" /></div>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">
          Henüz bildirim yok. Bir agent send_notification çağırınca ya da ekip çalışınca burada görünür.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((n) => <Row key={n.id} n={n} />)}
        </div>
      )}
    </div>
  );
}

function Row({ n }: { n: AppNotification }) {
  const Lvl = n.level === "success" ? CheckCircle2 : n.level === "error" ? AlertTriangle : Info;
  const lvlColor = n.level === "success" ? "text-green-400" : n.level === "error" ? "text-red-400" : "text-zinc-400";
  const KindI = n.kind === "sent" ? Send : Activity;
  return (
    <div className={cn("rounded-xl border bg-zinc-900/40 p-3", n.is_read ? "border-zinc-800/60" : "border-indigo-500/30")}>
      <div className="flex items-start gap-2.5">
        <Lvl size={15} className={cn("mt-0.5 shrink-0", lvlColor)} />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-zinc-200">{n.title}</p>
          {n.body && <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-xs text-zinc-500">{n.body}</p>}
          <div className="mt-1 flex items-center gap-2 text-[10px] text-zinc-600">
            <span className="inline-flex items-center gap-1"><KindI size={10} />{n.kind === "sent" ? "gönderildi" : "sistem"}</span>
            {n.source && <span>· {n.source}</span>}
            <span>· {relativeTime(n.created_at)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
