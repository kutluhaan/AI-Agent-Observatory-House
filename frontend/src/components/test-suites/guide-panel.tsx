"use client";

import { useState } from "react";
import { BookOpen, X, GitCompare, BarChart2, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const ASSERTIONS = [
  { type: "response_contains", desc: "Çıktı bu metni içeriyor mu?" },
  { type: "response_not_contains", desc: "Çıktı bu metni içermiyor mu?" },
  { type: "response_equals", desc: "Çıktı tam olarak bu metin mi?" },
  { type: "response_regex", desc: "Çıktı regex'le eşleşiyor mu?" },
  { type: "tools_used", desc: "Bu tool'lar kullanıldı mı?" },
  { type: "tool_sequence", desc: "Bu sırayla çağrıldı mı?" },
  { type: "tool_called_with_args", desc: "Tool bu argümanlarla çağrıldı mı?" },
  { type: "no_tool_errors", desc: "Hiç tool hatası olmadı mı?" },
  { type: "no_pii", desc: "Çıktıda PII (e-mail, numara) var mı?" },
  { type: "not_refused", desc: "Geçerli isteği reddetmedi mi?" },
  { type: "steps_under", desc: "Adım sayısı bu sınırın altında mı?" },
  { type: "tokens_under", desc: "Token sayısı bu sınırın altında mı?" },
  { type: "cost_under", desc: "Maliyet (USD) bu sınırın altında mı?" },
  { type: "latency_under", desc: "Toplam süre (ms) bu sınırın altında mı?" },
];

const JUDGES = [
  { type: "task_completion", desc: "Görevi tamamladı mı? (skor 0–1)" },
  { type: "answer_correctness", desc: "Cevap doğru mu? (expected gerektirir)" },
  { type: "step_efficiency", desc: "Gereksiz adım olmadı mı?" },
  { type: "safety", desc: "Toksik/zararlı içerik yok mu?" },
  { type: "rubric", desc: "Serbest kritere göre değerlendirme" },
  { type: "output_quality", desc: "Çıktı kalitesi (netlik, özlülük)" },
];

function GuideContent() {
  const [flowOpen, setFlowOpen] = useState(true);
  const [assertOpen, setAssertOpen] = useState(true);
  const [judgeOpen, setJudgeOpen] = useState(false);

  return (
    <div className="flex flex-col gap-3 text-xs text-zinc-400">
      {/* Temel akış */}
      <div className="rounded-lg border border-zinc-800/80 overflow-hidden">
        <button
          type="button"
          onClick={() => setFlowOpen((o) => !o)}
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-900/60"
        >
          <span className="font-medium text-zinc-200 text-[11px]">Temel akış</span>
          <ChevronDown size={11} className={cn("ml-auto text-zinc-600 transition-transform", flowOpen && "rotate-180")} />
        </button>
        {flowOpen && (
          <div className="border-t border-zinc-800/60 px-3 pb-3 pt-2">
            <ol className="flex flex-col gap-1 list-decimal list-inside text-zinc-500 text-[11px]">
              <li><span className="text-zinc-400">YAML suite oluştur</span> — agent_id + cases</li>
              <li><span className="text-zinc-400">Run</span> — sıralı veya paralel</li>
              <li><span className="text-zinc-400">Sonuçlar</span> — passed/failed + trace linki</li>
              <li><span className="text-zinc-400">KPI</span> — geçme oranı, maliyet, süre trendi</li>
              <li><span className="text-zinc-400">A/B</span> — iki farklı system prompt karşılaştır</li>
            </ol>
            <div className="mt-2">
              <p className="mb-1 text-[10px] text-zinc-500">Minimal YAML</p>
              <pre className="overflow-x-auto rounded border border-zinc-800 bg-zinc-950/60 p-2 text-[10px] text-zinc-400 leading-relaxed">{`name: temel-test
agent_id: "<uuid>"
cases:
  - name: selamlama
    input: "Merhaba!"
    assertions:
      - type: response_contains
        value: "merhaba"
      - type: not_refused
        value: true`}</pre>
            </div>
            <div className="mt-2 flex gap-2 rounded border border-indigo-500/20 bg-indigo-500/5 p-2">
              <GitCompare size={11} className="mt-0.5 shrink-0 text-indigo-400" />
              <div>
                <p className="text-[10px] font-medium text-indigo-300">Tekrar & tutarlılık</p>
                <p className="text-[10px] text-zinc-600">Case'e <span className="text-zinc-400">repeat: 3</span> + <span className="text-zinc-400">min_pass_rate: 0.66</span> → 3'ten 2'si geçerse passed.</p>
              </div>
            </div>
            <div className="mt-2 flex gap-2 rounded border border-amber-500/20 bg-amber-500/5 p-2">
              <BarChart2 size={11} className="mt-0.5 shrink-0 text-amber-400" />
              <div>
                <p className="text-[10px] font-medium text-amber-300">A/B prompt deneyi</p>
                <p className="text-[10px] text-zinc-600">Detay sayfasında A/B butonu → farklı system prompt'larla aynı suite → sonuçlar karşılaştırılır.</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Assertion tipleri */}
      <div className="rounded-lg border border-zinc-800/80 overflow-hidden">
        <button
          type="button"
          onClick={() => setAssertOpen((o) => !o)}
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-900/60"
        >
          <span className="font-medium text-zinc-200 text-[11px]">Assertion tipleri</span>
          <ChevronDown size={11} className={cn("ml-auto text-zinc-600 transition-transform", assertOpen && "rotate-180")} />
        </button>
        {assertOpen && (
          <div className="border-t border-zinc-800/60 px-3 pb-3 pt-2 flex flex-col gap-0.5">
            {ASSERTIONS.map((a) => (
              <div key={a.type} className="flex gap-2">
                <span className="shrink-0 font-mono text-[10px] text-indigo-400 w-40">{a.type}</span>
                <span className="text-[10px] text-zinc-600">{a.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* LLM judge tipleri */}
      <div className="rounded-lg border border-zinc-800/80 overflow-hidden">
        <button
          type="button"
          onClick={() => setJudgeOpen((o) => !o)}
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-900/60"
        >
          <span className="font-medium text-zinc-200 text-[11px]">LLM judge tipleri</span>
          <ChevronDown size={11} className={cn("ml-auto text-zinc-600 transition-transform", judgeOpen && "rotate-180")} />
        </button>
        {judgeOpen && (
          <div className="border-t border-zinc-800/60 px-3 pb-3 pt-2 flex flex-col gap-0.5">
            <p className="mb-1 text-[10px] text-zinc-600">Token harcar; <code className="text-zinc-500">judges:</code> bloğunda tanımlanınca çalışır.</p>
            {JUDGES.map((j) => (
              <div key={j.type} className="flex gap-2">
                <span className="shrink-0 font-mono text-[10px] text-violet-400 w-36">{j.type}</span>
                <span className="text-[10px] text-zinc-600">{j.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** Sağ kenardan açılan slide-over drawer + tetikleyici buton */
export function GuideDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Trigger butonu */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-lg border border-zinc-700/60 bg-zinc-900/60 px-2.5 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-200"
      >
        <BookOpen size={13} />
        Rehber
      </button>

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Drawer */}
      <div
        className={cn(
          "fixed right-0 top-0 z-50 h-full w-80 overflow-y-auto border-l border-zinc-800 bg-zinc-950 p-4 shadow-2xl transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="mb-4 flex items-center gap-2">
          <BookOpen size={14} className="text-indigo-400" />
          <span className="text-sm font-medium text-zinc-200">Test suite rehberi</span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="ml-auto text-zinc-600 hover:text-zinc-300"
          >
            <X size={15} />
          </button>
        </div>
        <GuideContent />
      </div>
    </>
  );
}
