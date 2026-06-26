"use client";

import { useState } from "react";
import { BookOpen, ChevronDown, GitCompare, BarChart2 } from "lucide-react";
import { cn } from "@/lib/utils";

const ASSERTIONS = [
  { type: "response_contains", desc: "Çıktı bu metni içeriyor mu?" },
  { type: "response_not_contains", desc: "Çıktı bu metni içermiyor mu?" },
  { type: "response_equals", desc: "Çıktı tam olarak bu metin mi?" },
  { type: "response_regex", desc: "Çıktı regex'le eşleşiyor mu?" },
  { type: "tools_used", desc: "Bu tool'lar kullanıldı mı? (alt-küme)" },
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
  { type: "task_completion", desc: "Görevi tamamladı mı? (skor 0–1, eşik 0.7)" },
  { type: "answer_correctness", desc: "Cevap doğru mu? (expected gerektirir)" },
  { type: "step_efficiency", desc: "Gereksiz adım olmadı mı?" },
  { type: "safety", desc: "Toksik/zararlı içerik yok mu?" },
  { type: "rubric", desc: "Serbest kritere göre değerlendirme (criteria alanı)" },
  { type: "output_quality", desc: "Çıktı kalitesi (netlik, özlülük, format)" },
];

export function GuidePanel({ defaultOpen = true }: { defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-8 rounded-xl border border-zinc-800/80 bg-zinc-900/30">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left transition-colors hover:bg-zinc-900/50"
      >
        <BookOpen size={14} className="shrink-0 text-indigo-400" />
        <span className="text-sm font-medium text-zinc-200">Test suites nasıl çalışır?</span>
        <ChevronDown size={13} className={cn("ml-auto shrink-0 text-zinc-500 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-zinc-800/60 px-4 pb-4 pt-3 text-xs text-zinc-400">
          <div className="grid gap-6 sm:grid-cols-2">
            {/* Sol: akış */}
            <div className="flex flex-col gap-3">
              <div>
                <p className="mb-1 font-medium text-zinc-200">Temel akış</p>
                <ol className="flex flex-col gap-1 list-decimal list-inside text-zinc-500">
                  <li><span className="text-zinc-400">YAML suite oluştur</span> — agent_id + cases</li>
                  <li><span className="text-zinc-400">Run</span> — sıralı veya paralel</li>
                  <li><span className="text-zinc-400">Sonuçlar</span> — passed/failed + trace linki</li>
                  <li><span className="text-zinc-400">KPI</span> — geçme oranı, maliyet, süre trendi</li>
                  <li><span className="text-zinc-400">A/B</span> — iki farklı system prompt karşılaştır</li>
                </ol>
              </div>
              <div>
                <p className="mb-1 font-medium text-zinc-200">Minimal YAML</p>
                <pre className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950/60 p-2.5 text-[11px] text-zinc-400">{`name: temel-test
agent_id: "<agent-uuid>"
cases:
  - name: selamlama-testi
    input: "Merhaba!"
    assertions:
      - type: response_contains
        value: "merhaba"
      - type: not_refused
        value: true`}</pre>
              </div>
              <div className="flex items-start gap-2 rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-2.5">
                <GitCompare size={13} className="mt-0.5 shrink-0 text-indigo-400" />
                <div>
                  <p className="font-medium text-indigo-300">A/B prompt deneyi</p>
                  <p className="mt-0.5 text-zinc-500">Suite detay sayfasında <span className="text-zinc-400">A/B test</span> butonu → farklı system prompt'larla aynı suite'i çalıştır → sonuçlar yan yana karşılaştırılır.</p>
                </div>
              </div>
              <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2.5">
                <BarChart2 size={13} className="mt-0.5 shrink-0 text-amber-400" />
                <div>
                  <p className="font-medium text-amber-300">Tekrar & tutarlılık</p>
                  <p className="mt-0.5 text-zinc-500">Case'e <span className="text-zinc-400">repeat: 3</span> + <span className="text-zinc-400">min_pass_rate: 0.66</span> ekle → 3 çalışmanın en az 2'si geçerse "passed".</p>
                </div>
              </div>
            </div>
            {/* Sağ: assertion + judge tablosu */}
            <div className="flex flex-col gap-3">
              <div>
                <p className="mb-1 font-medium text-zinc-200">Assertion tipleri</p>
                <div className="flex flex-col gap-0.5">
                  {ASSERTIONS.map((a) => (
                    <div key={a.type} className="flex gap-2">
                      <span className="w-44 shrink-0 font-mono text-[10px] text-indigo-400">{a.type}</span>
                      <span className="text-[10px] text-zinc-500">{a.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-1 font-medium text-zinc-200">LLM judge tipleri</p>
                <p className="mb-1 text-[10px] text-zinc-600">Token harcar; <code className="text-zinc-500">judges:</code> bloğunda tanımlanınca çalışır.</p>
                <div className="flex flex-col gap-0.5">
                  {JUDGES.map((j) => (
                    <div key={j.type} className="flex gap-2">
                      <span className="w-36 shrink-0 font-mono text-[10px] text-violet-400">{j.type}</span>
                      <span className="text-[10px] text-zinc-500">{j.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
