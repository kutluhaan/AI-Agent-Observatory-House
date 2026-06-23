"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, StickyNote, CheckCircle2, ChevronDown, Wrench } from "lucide-react";
import { api, type TeamRunDetail, type TeamRunMessage } from "@/lib/api";
import { roleIcon, roleColor } from "@/lib/team-roles";
import { subscribeTeamRuns } from "@/lib/ws";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";

export default function TeamRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<TeamRunDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get<TeamRunDetail>(`/team-runs/${id}`).then(setData).catch(() => setError("Bulunamadı."));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // C2: canlı — WS ping geldiğinde bu run'ı yeniden çek
  useEffect(() => {
    const unsub = subscribeTeamRuns((ev) => {
      if (ev.run_id === id) load();
    });
    return unsub;
  }, [id, load]);

  // WS düşerse yedek: çalışırken yavaş poll
  useEffect(() => {
    if (!data || (data.run.status !== "running" && data.run.status !== "pending")) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [data, load]);

  if (error) return <div className="mx-auto max-w-2xl px-6 py-10"><Alert variant="error">{error}</Alert></div>;
  if (!data) return <div className="flex justify-center py-20"><Spinner className="h-5 w-5" /></div>;

  const { run, messages } = data;
  const board = messages.filter((m) => m.kind === "board");

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link href={`/teams/${run.team_id}`} className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Ekip
      </Link>

      <div className="mb-4 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-zinc-100">Ekip çalıştırması</h1>
        <div className="flex items-center gap-2">
          {(run.status === "running" || run.status === "pending") && <Spinner className="h-3.5 w-3.5" />}
          <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        </div>
      </div>

      <div className="mb-6 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
        <p className="text-[11px] uppercase tracking-wide text-zinc-600">Görev</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-300">{run.input}</p>
      </div>

      {run.error_message && <Alert variant="error" className="mb-6">{run.error_message}</Alert>}

      {/* Final output */}
      {run.final_output && (
        <div className="mb-6 rounded-xl border border-green-500/20 bg-green-500/5 p-4">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-green-400">
            <CheckCircle2 size={12} />Final çıktı
          </p>
          <div className="text-sm text-zinc-200">
            <Markdown>{run.final_output}</Markdown>
          </div>
        </div>
      )}

      {/* Paylaşılan pano */}
      {board.length > 0 && (
        <>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Paylaşılan pano</h2>
          <div className="mb-6 flex flex-col gap-2">
            {board.map((m) => (
              <div key={m.id} className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
                <p className="flex items-center gap-1.5 text-xs text-amber-300">
                  <StickyNote size={12} />
                  {m.title} <span className="text-zinc-600">· {m.from_role}</span>
                </p>
                <p className="mt-1 whitespace-pre-wrap text-xs text-zinc-400">{m.content}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Delegasyon timeline'ı */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">İşbirliği akışı</h2>
      {messages.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">
          {run.status === "running" || run.status === "pending" ? "Çalışıyor…" : "Mesaj yok."}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {messages.map((m) => <MessageRow key={m.id} m={m} />)}
        </div>
      )}
    </div>
  );
}

function MessageRow({ m }: { m: TeamRunMessage }) {
  const [open, setOpen] = useState(false);
  // board üstte ayrı gösterildi; final, sayfa başında "Final çıktı" kutusunda
  if (m.kind === "board" || m.kind === "final") return null;

  // C1/C2: üye tool çağrısı — delegasyonun altına girintili, minimal
  if (m.kind === "tool") {
    const RI = m.from_role ? roleIcon(m.from_role) : Wrench;
    return (
      <div className="ml-6 rounded-lg border border-zinc-800/50 bg-zinc-950/30">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left transition-colors hover:bg-zinc-900/40"
        >
          <RI size={11} className={m.from_role ? roleColor(m.from_role) : "text-amber-400"} />
          <Wrench size={10} className="text-amber-400" />
          <span className="shrink-0 text-[11px] font-medium text-zinc-400">{m.title}</span>
          {!open && <span className="min-w-0 flex-1 truncate text-[11px] text-zinc-600">· {m.content}</span>}
          <ChevronDown size={11} className={cn("ml-auto shrink-0 text-zinc-700 transition-transform", open && "rotate-180")} />
        </button>
        {open && (
          <p className="max-h-56 overflow-y-auto whitespace-pre-wrap border-t border-zinc-800/50 px-3 py-1.5 text-[11px] text-zinc-400">
            {m.content}
          </p>
        )}
      </div>
    );
  }

  const isDelegate = m.kind === "delegate";
  const FromI = m.from_role ? roleIcon(m.from_role) : null;
  const ToI = m.to_role ? roleIcon(m.to_role) : null;
  return (
    <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-zinc-900/50"
      >
        <span className="flex shrink-0 items-center gap-1 text-[11px]">
          {FromI && <FromI size={12} className={roleColor(m.from_role!)} />}
          <span className="text-zinc-300">{m.from_role}</span>
          <ArrowRight size={10} className="text-zinc-600" />
          {ToI && <ToI size={12} className={roleColor(m.to_role!)} />}
          <span className="text-zinc-300">{m.to_role}</span>
          <span className="text-zinc-600">· {isDelegate ? "delege" : "sonuç"}</span>
        </span>
        {!open && <span className="min-w-0 flex-1 truncate text-[11px] text-zinc-600">{m.content}</span>}
        <ChevronDown size={12} className={cn("ml-auto shrink-0 text-zinc-600 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <p className="max-h-72 overflow-y-auto whitespace-pre-wrap border-t border-zinc-800/60 px-3 py-2 text-xs text-zinc-300">
          {m.content}
        </p>
      )}
    </div>
  );
}
