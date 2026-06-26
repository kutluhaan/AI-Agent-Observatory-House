"use client";

import React, { useState } from "react";
import { BookOpen, X, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

type SectionProps = {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
};

function Section({ title, children, defaultOpen = false }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-zinc-800/80 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-zinc-900/60 transition-colors"
      >
        <span className="font-medium text-zinc-200 text-xs">{title}</span>
        <ChevronDown size={12} className={cn("ml-auto text-zinc-600 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-zinc-800/60 px-3 pb-3 pt-2.5">
          {children}
        </div>
      )}
    </div>
  );
}

function Code({ children }: { children: string }) {
  return (
    <pre className="mt-1.5 overflow-x-auto rounded border border-zinc-800 bg-zinc-950/70 p-2.5 text-[10.5px] text-zinc-300 leading-relaxed font-mono whitespace-pre-wrap">
      {children}
    </pre>
  );
}

function Mono({ children }: { children: string }) {
  return (
    <span className="inline-block rounded px-1 py-0.5 font-mono text-[10px] text-indigo-400 bg-indigo-500/10">
      {children}
    </span>
  );
}

function Row({ label, desc }: { label: string; desc: string }) {
  return (
    <div className="flex gap-2 items-start py-0.5">
      <span className="shrink-0 font-mono text-[10.5px] text-indigo-400 w-44">{label}</span>
      <span className="text-[10.5px] text-zinc-500 leading-snug">{desc}</span>
    </div>
  );
}

function JudgeRow({ label, desc }: { label: string; desc: string }) {
  return (
    <div className="flex gap-2 items-start py-0.5">
      <span className="shrink-0 font-mono text-[10.5px] text-violet-400 w-40">{label}</span>
      <span className="text-[10.5px] text-zinc-500 leading-snug">{desc}</span>
    </div>
  );
}

function Note({ color, title, children }: { color: "amber" | "zinc"; title: string; children: React.ReactNode }) {
  const border = color === "amber" ? "border-amber-500/20 bg-amber-500/5" : "border-zinc-700/40 bg-zinc-900/40";
  const titleColor = color === "amber" ? "text-amber-300" : "text-zinc-300";
  return (
    <div className={cn("rounded border px-2.5 py-1.5", border)}>
      <p className={cn("text-[10.5px] font-medium", titleColor)}>{title}</p>
      <p className="text-[10px] text-zinc-600">{children}</p>
    </div>
  );
}

function GuideContent() {
  return (
    <div className="flex flex-col gap-2 text-xs">

      <Section title="Test suite nedir?" defaultOpen={true}>
        <p className="text-[11px] text-zinc-400 leading-relaxed">
          Test suite, bir agent'ı tanımlanmış girdilerle çalıştırıp çıktısını otomatik olarak değerlendiren bir senaryo koleksiyonudur.
          Her <Mono>case</Mono> bir test durumudur: agent'a bir <Mono>input</Mono> gönderilir,
          dönen yanıt <Mono>assertions</Mono> ile deterministik olarak, <Mono>judges</Mono> ile LLM tarafından değerlendirilir.
        </p>
        <p className="mt-2 text-[11px] text-zinc-500 leading-relaxed">
          Suite'ler YAML formatında yazılır, A/B prompt deneyi yapılabilir ve zaman içindeki performans trendi KPI grafiğiyle izlenebilir.
        </p>
      </Section>

      <Section title="YAML yapısı" defaultOpen={true}>
        <Code>{`name: suite-adı              # zorunlu
description: "açıklama"      # opsiyonel
agent_id: "<uuid>"           # zorunlu (suite seviyesi)

cases:
  - name: test-adı           # zorunlu
    agent_id: "<uuid>"       # opsiyonel (case override)
    input: "kullanıcı mesajı"

    assertions:              # deterministik kontroller
      - type: response_contains
        value: "beklenen metin"

    judges:                  # LLM değerlendirmesi (token harcar)
      - type: task_completion

    repeat: 3                # tutarlılık: kaç kez çalıştır
    min_pass_rate: 0.66      # en az %66si geçmeli`}</Code>
        <p className="mt-2 text-[10.5px] text-zinc-600">
          <span className="text-zinc-400">agent_id</span> suite seviyesinde tanımlanırsa tüm case'ler onu kullanır. Case seviyesinde tanımlanırsa suite tanımını ezer.
        </p>
      </Section>

      <Section title="Assertion tipleri" defaultOpen={true}>
        <p className="mb-2 text-[10.5px] text-zinc-500">Token harcamaz, hızlıdır. Her assertion <Mono>type</Mono> + <Mono>value</Mono> içerir.</p>

        <p className="mb-1 mt-1 text-[10.5px] font-medium text-zinc-400">Çıktı (metin)</p>
        <div className="flex flex-col mb-2">
          <Row label="response_contains" desc='value: "metin" — çıktıda bu metin geçmeli' />
          <Row label="response_not_contains" desc='value: "metin" — bu metin geçmemeli' />
          <Row label="response_equals" desc='value: "tam metin" — çıktı bununla birebir eşleşmeli' />
          <Row label="response_regex" desc='value: "\\bkaynak\\b" — regex eşleşmesi' />
        </div>

        <p className="mb-1 text-[10.5px] font-medium text-zinc-400">Tool kullanımı (trajectory)</p>
        <div className="flex flex-col mb-2">
          <Row label="tools_used" desc='value: ["web_search", "write_file"] — bu toollar çağrılmış olmalı (alt-küme)' />
          <Row label="tool_sequence" desc='value: ["web_search", "write_file"] — bu sırayla çağrılmalı (aralarında başka olabilir)' />
          <Row label="tool_called_with_args" desc='value: {name: "write_file", args: {path: "out.md"}} — bu argümanlarla çağrılmalı' />
          <Row label="no_tool_errors" desc="value: true — hiçbir tool hata döndürmemeli" />
        </div>

        <p className="mb-1 text-[10.5px] font-medium text-zinc-400">Güvenlik ve davranış</p>
        <div className="flex flex-col mb-2">
          <Row label="no_pii" desc="value: true — çıktıda e-posta, TC kimlik, kredi kartı vb. olmamalı" />
          <Row label="not_refused" desc="value: true — geçerli isteği reddetmemiş olmalı" />
        </div>

        <p className="mb-1 text-[10.5px] font-medium text-zinc-400">Operasyonel bütçe</p>
        <div className="flex flex-col mb-2">
          <Row label="steps_under" desc="value: 8 — toplam adım sayısı bu değerin altında olmalı" />
          <Row label="tokens_under" desc="value: 40000 — toplam token kullanımı bu değerin altında olmalı" />
          <Row label="cost_under" desc="value: 0.05 — USD cinsinden maliyet bu değerin altında olmalı" />
          <Row label="latency_under" desc="value: 60000 — toplam süre ms cinsinden bu değerin altında olmalı" />
        </div>

        <Code>{`assertions:
  - type: tools_used
    value: ["web_search", "read_urls"]
  - type: tool_called_with_args
    value:
      name: "write_file"
      args:
        path: "output/rapor.md"
  - type: steps_under
    value: 10
  - type: cost_under
    value: 0.10`}</Code>
      </Section>

      <Section title="LLM judge tipleri">
        <p className="mb-2 text-[10.5px] text-zinc-500">
          Token harcar (~200-500 token/judge). <Mono>judges:</Mono> bloğu tanımlanmadıysa çalışmaz.
          Skor 0-1 arasındadır, <Mono>threshold</Mono> tanımlanmazsa varsayılan 0.7 dir.
        </p>
        <div className="flex flex-col mb-2">
          <JudgeRow label="task_completion" desc="Görevi tamamladı mı? Eşik: 0.7" />
          <JudgeRow label="answer_correctness" desc="Cevap doğru mu? expected alanı gerektirir" />
          <JudgeRow label="step_efficiency" desc="Gereksiz adım var mı? Eşik: 0.6" />
          <JudgeRow label="safety" desc="Toksik/zararlı/PII içerik yok mu? Eşik: 0.9" />
          <JudgeRow label="rubric" desc="Serbest kriter. criteria alanı gerektirir" />
          <JudgeRow label="output_quality" desc="Netlik, özlülük, format kalitesi" />
        </div>
        <Code>{`judges:
  - type: task_completion
    threshold: 0.8
  - type: rubric
    criteria: "Cevap Türkce olmali ve en az
               bir kaynak icermeli."
  - type: safety
    threshold: 0.95`}</Code>
      </Section>

      <Section title="Senaryo modu (çok-turlu)">
        <p className="mb-2 text-[10.5px] text-zinc-500">
          <Mono>input</Mono> yerine <Mono>steps</Mono> kullanıldığında agent çok-turlu diyalog senaryosunda test edilir.
          Her adım bir konuşma turu oluşturur; önceki yanıt konuşma geçmişine eklenir.
        </p>
        <Code>{`cases:
  - name: cok-turlu-senaryo
    steps:
      - input: "Merhaba, yardim eder misin?"
        assertions:
          - type: not_refused
            value: true
      - input: "Istanbul hava durumu nedir?"
        assertions:
          - type: response_contains
            value: "Istanbul"
          - type: tools_used
            value: ["web_search"]
      - input: "Tesekkurler, ozet verir misin?"
        assertions:
          - type: task_completion
            threshold: 0.7`}</Code>
      </Section>

      <Section title="Dataset modu (CSV/JSONL)">
        <p className="mb-2 text-[10.5px] text-zinc-500">
          Büyük veri setlerini otomatik case'e dönüştürür. Her satır bir test case olur.
        </p>
        <p className="mb-1 text-[10.5px] font-medium text-zinc-400">CSV formatı</p>
        <Code>{`input,expected
"Istanbul nerede?","Turkiye"
"Python nedir?","programlama dili"`}</Code>
        <p className="mt-2 mb-1 text-[10.5px] font-medium text-zinc-400">JSONL formatı</p>
        <Code>{`{"input": "Istanbul nerede?", "expected": "Turkiye"}
{"input": "Python nedir?", "expected": "programlama dili"}`}</Code>
        <p className="mt-2 text-[10.5px] text-zinc-600">
          <span className="text-zinc-400">expected</span> boş bırakılırsa assertion eklenmez; sadece agent çalıştırılır.
        </p>
      </Section>

      <Section title="Tekrar ve tutarlılık">
        <p className="mb-2 text-[10.5px] text-zinc-500">
          LLM deterministik değildir. <Mono>repeat</Mono> ile aynı case birden fazla çalıştırılır,
          <Mono>min_pass_rate</Mono> ile kaçının geçmesi gerektiği belirlenir.
        </p>
        <Code>{`cases:
  - name: tutarlilik-testi
    input: "Baskent sehir hangisi?"
    assertions:
      - type: response_contains
        value: "Ankara"
    repeat: 5
    min_pass_rate: 0.8   # 5'ten 4'u gecmeli`}</Code>
      </Section>

      <Section title="A/B prompt deneyi">
        <p className="mb-2 text-[10.5px] text-zinc-500">
          Aynı suite'i farklı system prompt'larla çalıştırıp hangi prompt'un daha iyi performans gösterdiğini karşılaştırır.
          Suite detay sayfasındaki <Mono>A/B test</Mono> butonundan başlatılır.
        </p>
        <p className="text-[10.5px] text-zinc-600">
          Her varyant ayrı bir experiment run oluşturur. Sonuçlar yan yana: geçme oranı, maliyet, süre karşılaştırılır.
          Agent'ın system prompt'u kalıcı olarak değişmez — sadece bu çalıştırma için override edilir.
        </p>
      </Section>

      <Section title="Paralel vs sıralı çalıştırma">
        <div className="flex flex-col gap-1.5">
          <div className="rounded border border-zinc-800/60 px-2.5 py-1.5">
            <p className="text-[10.5px] font-medium text-zinc-300">Sıralı</p>
            <p className="text-[10px] text-zinc-600">Case'ler sırayla çalışır. API rate limit riski düşük.</p>
          </div>
          <div className="rounded border border-zinc-800/60 px-2.5 py-1.5">
            <p className="text-[10.5px] font-medium text-zinc-300">Paralel</p>
            <p className="text-[10px] text-zinc-600">Tüm case'ler aynı anda çalışır. Çok daha hızlı ama Gemini free-tier'da 429 hatası alabilirsin.</p>
          </div>
        </div>
      </Section>

      <Section title="KPI ve trend izleme">
        <p className="text-[10.5px] text-zinc-500 leading-relaxed">
          Suite detay sayfasındaki KPI bölümünde takip etmek istediğin metrikleri seç.
          Her run'dan sonra grafik güncellenir; geçme oranı, ortalama maliyet ve süre trendi görüntülenir.
        </p>
        <p className="mt-1.5 text-[10.5px] text-zinc-600">
          Seçilebilir KPI'lar: geçme oranı, başarısız case sayısı, ortalama token kullanımı, ortalama maliyet (USD), ortalama süre (ms).
        </p>
      </Section>

      <Section title="Ipuçları ve sık hatalar">
        <div className="flex flex-col gap-1.5">
          <Note color="amber" title="agent_id UUID olmali">
            Agent detay sayfasından kopyala. Agent adı değil, UUID gir.
          </Note>
          <Note color="amber" title="response_contains büyük/küçük harf duyarlıdır">
            Beklediğin metin küçük harfse value'yu küçük yaz ya da response_regex kullan.
          </Note>
          <Note color="amber" title="Judge token harcar">
            Her judge çağrısı ~200-500 token tüketir. Gemini free-tier'da az judge kullan.
          </Note>
          <Note color="zinc" title="tool_called_with_args kısmi eşleşir">
            args içinde sadece kontrol etmek istediğin alanları yaz; fazlası yoksayılır.
          </Note>
          <Note color="zinc" title="Suite oluşturduktan sonra YAML düzenlenebilir">
            Suite detay sayfasında YAML alanı direkt düzenlenebilir.
          </Note>
        </div>
      </Section>

    </div>
  );
}

export function GuideDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-zinc-700/60 bg-zinc-900/60 px-2.5 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-200"
      >
        <BookOpen size={13} />
        Rehber
      </button>

      <div
        className={cn(
          "fixed right-0 top-0 z-50 h-full w-[480px] overflow-y-auto border-l border-zinc-800 bg-zinc-950 shadow-2xl transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-zinc-800/80 bg-zinc-950 px-4 py-3">
          <BookOpen size={14} className="text-indigo-400 shrink-0" />
          <span className="text-sm font-medium text-zinc-200">Test suite rehberi</span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="ml-auto text-zinc-600 hover:text-zinc-300 transition-colors"
          >
            <X size={15} />
          </button>
        </div>
        <div className="p-4">
          <GuideContent />
        </div>
      </div>
    </>
  );
}
