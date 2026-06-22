"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, StickyNote, CheckCircle2 } from "lucide-react";
import { api, type TeamRunDetail, type TeamRunMessage } from "@/lib/api";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function TeamRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<TeamRunDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get<TeamRunDetail>(`/team-runs/${id}`).then(setData).catch(() => setError("Bulunamadı."));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // çalışırken poll
  useEffect(() => {
    if (!data || (data.run.status !== "running" && data.run.status !== "pending")) return;
    const t = setInterval(load, 2500);
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
          <p className="mb-1 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-green-400">
            <CheckCircle2 size={12} />Final çıktı
          </p>
          <p className="whitespace-pre-wrap text-sm text-zinc-200">{run.final_output}</p>
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
  if (m.kind === "board") return null; // panoda gösterildi
  const isDelegate = m.kind === "delegate";
  const isResult = m.kind === "result";
  const isFinal = m.kind === "final";
  return (
    <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
      <p className="flex items-center gap-1.5 text-[11px] text-zinc-500">
        {isDelegate && <><Badge variant="indigo">{m.from_role}</Badge><ArrowRight size={11} /><Badge variant="zinc">{m.to_role}</Badge><span className="text-zinc-600">delege</span></>}
        {isResult && <><Badge variant="zinc">{m.from_role}</Badge><ArrowRight size={11} /><Badge variant="indigo">{m.to_role}</Badge><span className="text-zinc-600">sonuç</span></>}
        {isFinal && <><CheckCircle2 size={11} className="text-green-400" /><span className="text-green-400">final</span></>}
      </p>
      <p className="mt-1.5 whitespace-pre-wrap text-xs text-zinc-300">{m.content}</p>
    </div>
  );
}
