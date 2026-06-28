"use client";

import React, { useEffect, useState } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { type Node } from "@xyflow/react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ConfigPanelProps {
  node: Node;
  allNodes: Node[];
  onClose: () => void;
  onUpdate: (id: string, data: Record<string, unknown>) => void;
}

// ── Integration metadata ──────────────────────────────────────

type ParamDef = { key: string; label: string; placeholder?: string; hint?: string };
type OpDef = { value: string; label: string; params: ParamDef[] };

const SERVICE_OPS: Record<string, OpDef[]> = {
  gmail: [
    { value: "gmail_search", label: "Mailleri Ara", params: [
      { key: "query", label: "Sorgu", placeholder: "from:example@gmail.com" },
      { key: "max_results", label: "Maks sonuç", placeholder: "5" },
    ]},
    { value: "gmail_read", label: "Mail Oku", params: [
      { key: "message_id", label: "Mesaj ID", placeholder: "{{node-id.output}}" },
    ]},
    { value: "gmail_send", label: "Mail Gönder", params: [
      { key: "to", label: "Alıcı", placeholder: "user@example.com" },
      { key: "subject", label: "Konu", placeholder: "Konu" },
      { key: "body", label: "İçerik", placeholder: "{{prev-node.output}}" },
    ]},
  ],
  gcalendar: [
    { value: "calendar_list_events", label: "Etkinlikleri Listele", params: [
      { key: "max_results", label: "Maks sonuç", placeholder: "10" },
    ]},
    { value: "calendar_create_event", label: "Etkinlik Oluştur", params: [
      { key: "summary", label: "Başlık", placeholder: "Toplantı" },
      { key: "start", label: "Başlangıç (ISO)", placeholder: "2024-01-15T09:00:00" },
      { key: "end", label: "Bitiş (ISO)", placeholder: "2024-01-15T10:00:00" },
      { key: "description", label: "Açıklama", placeholder: "{{node-id.output}}" },
    ]},
  ],
  gdrive: [
    { value: "drive_search", label: "Dosya Ara", params: [
      { key: "query", label: "Sorgu", placeholder: "name contains 'rapor'" },
      { key: "max_results", label: "Maks sonuç", placeholder: "10" },
    ]},
    { value: "drive_read_file", label: "Dosya Oku", params: [
      { key: "file_id", label: "Dosya ID", placeholder: "{{node-id.output}}" },
    ]},
  ],
  github: [
    { value: "github_search", label: "Ara", params: [
      { key: "query", label: "Sorgu", placeholder: "repo:owner/name bug" },
      { key: "kind", label: "Tür", placeholder: "repositories / code / issues" },
    ]},
    { value: "github_repo_info", label: "Repo Bilgisi", params: [
      { key: "repo", label: "Repo", placeholder: "owner/repo-name" },
    ]},
    { value: "github_issues", label: "Issue'lar", params: [
      { key: "repo", label: "Repo", placeholder: "owner/repo-name" },
      { key: "state", label: "Durum", placeholder: "open / closed / all" },
    ]},
    { value: "github_read_file", label: "Dosya Oku", params: [
      { key: "repo", label: "Repo", placeholder: "owner/repo-name" },
      { key: "path", label: "Yol", placeholder: "src/main.py" },
      { key: "ref", label: "Branch/SHA", placeholder: "main" },
    ]},
  ],
  db: [
    { value: "sql_query", label: "Sorgu Çalıştır", params: [
      { key: "query", label: "SQL", placeholder: "SELECT * FROM users LIMIT 10" },
      { key: "connection", label: "Bağlantı adı", placeholder: "(boşsa varsayılan)" },
    ]},
    { value: "sql_schema", label: "Şema", params: [
      { key: "connection", label: "Bağlantı adı", placeholder: "(boşsa varsayılan)" },
    ]},
    { value: "sql_sample", label: "Örnek Veri", params: [
      { key: "table", label: "Tablo", placeholder: "users" },
      { key: "limit", label: "Limit", placeholder: "10" },
      { key: "connection", label: "Bağlantı adı", placeholder: "(boşsa varsayılan)" },
    ]},
  ],
  mcp: [
    { value: "mcp_tool", label: "MCP Araç Çağır", params: [
      { key: "server_id", label: "Sunucu UUID", placeholder: "mcp-server uuid" },
      { key: "tool_name", label: "Araç adı", placeholder: "tool_name" },
      { key: "tool_params", label: "Parametreler (JSON)", placeholder: '{"key": "value"}', hint: "{{node_id.output}} template desteklenmez — JSON literal girin." },
    ]},
  ],
  http: [
    { value: "http_tool", label: "HTTP Araç Çağır", params: [
      { key: "tool_id", label: "Araç UUID", placeholder: "custom-tool uuid" },
      { key: "tool_params", label: "Parametreler (JSON)", placeholder: '{"key": "value"}' },
    ]},
  ],
};

// ── Helpers ───────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-medium text-zinc-500 uppercase tracking-wide">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:border-indigo-500 focus:outline-none";
const textareaCls = cn(inputCls, "resize-none leading-relaxed");

// ── Main component ────────────────────────────────────────────

export function ConfigPanel({ node, allNodes, onClose, onUpdate }: ConfigPanelProps) {
  const [data, setData] = useState<Record<string, unknown>>(
    (node.data as Record<string, unknown>) ?? {}
  );

  useEffect(() => {
    setData((node.data as Record<string, unknown>) ?? {});
  }, [node.id]);

  const set = (key: string, val: unknown) => setData((d) => ({ ...d, [key]: val }));

  const save = () => {
    onUpdate(node.id, data);
    onClose();
  };

  const conditions = (data.conditions as Array<{ handle: string; label: string; condition?: string }>) ?? [];
  const bodyNodeIds = (data.body_node_ids as string[]) ?? [];
  const candidateNodes = allNodes.filter((n) => n.id !== node.id && n.type !== "start" && n.type !== "end");

  // Integration
  const service = (data.service as string) ?? "http";
  const operation = (data.operation as string) ?? "";
  const params = (data.params as Record<string, string>) ?? {};
  const currentOps = SERVICE_OPS[service] ?? [];
  const currentOp = currentOps.find((o) => o.value === operation) ?? currentOps[0];
  const setParam = (key: string, val: string) =>
    set("params", { ...params, [key]: val });

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-zinc-800/80 bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 px-4 py-3">
        <span className="text-xs font-semibold text-zinc-200">Node Ayarları</span>
        <button onClick={onClose} className="rounded p-1 text-zinc-600 hover:text-zinc-300">
          <X size={14} />
        </button>
      </div>

      {/* Fields */}
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {node.type !== "note" && (
          <Field label="Ad">
            <input
              className={inputCls}
              value={(data.label as string) ?? ""}
              onChange={(e) => set("label", e.target.value)}
              placeholder="Node adı"
            />
          </Field>
        )}

        {/* ── Start ── */}
        {node.type === "start" && (
          <Field label="Tetikleyici">
            <select
              className={inputCls}
              value={(data.trigger_kind as string) ?? "manual"}
              onChange={(e) => set("trigger_kind", e.target.value)}
            >
              <option value="manual">Manuel</option>
              <option value="schedule">Zamanlama (cron)</option>
              <option value="event">Event</option>
            </select>
            {data.trigger_kind === "schedule" && (
              <input
                className={cn(inputCls, "mt-1.5")}
                value={(data.cron as string) ?? ""}
                onChange={(e) => set("cron", e.target.value)}
                placeholder="0 9 * * 1 (Pazartesi 09:00)"
              />
            )}
          </Field>
        )}

        {/* ── Agent ── */}
        {node.type === "agent" && (
          <Field label="Agent ID">
            <input
              className={inputCls}
              value={(data.agent_id as string) ?? ""}
              onChange={(e) => set("agent_id", e.target.value)}
              placeholder="uuid"
            />
          </Field>
        )}

        {/* ── Team ── */}
        {node.type === "team" && (
          <Field label="Ekip ID">
            <input
              className={inputCls}
              value={(data.team_id as string) ?? ""}
              onChange={(e) => set("team_id", e.target.value)}
              placeholder="uuid"
            />
          </Field>
        )}

        {/* ── Integration ── */}
        {node.type === "integration" && (
          <>
            <Field label="Servis">
              <select
                className={inputCls}
                value={service}
                onChange={(e) => {
                  const newService = e.target.value;
                  const firstOp = SERVICE_OPS[newService]?.[0]?.value ?? "";
                  set("service", newService);
                  set("operation", firstOp);
                  set("params", {});
                }}
              >
                <option value="gmail">Gmail</option>
                <option value="gcalendar">Google Calendar</option>
                <option value="gdrive">Google Drive</option>
                <option value="github">GitHub</option>
                <option value="db">Veritabanı (SQL)</option>
                <option value="mcp">MCP Server</option>
                <option value="http">HTTP Araç</option>
              </select>
            </Field>

            {currentOps.length > 0 && (
              <Field label="Operasyon">
                <select
                  className={inputCls}
                  value={operation || currentOps[0]?.value}
                  onChange={(e) => {
                    set("operation", e.target.value);
                    set("params", {});
                  }}
                >
                  {currentOps.map((op) => (
                    <option key={op.value} value={op.value}>{op.label}</option>
                  ))}
                </select>
              </Field>
            )}

            {currentOp && currentOp.params.length > 0 && (
              <Field label="Parametreler">
                <div className="flex flex-col gap-2">
                  {currentOp.params.map((p) => (
                    <div key={p.key} className="flex flex-col gap-0.5">
                      <span className="text-[10px] text-zinc-500">{p.label}</span>
                      <input
                        className={cn(inputCls, "font-mono text-[11px]")}
                        value={params[p.key] ?? ""}
                        onChange={(e) => setParam(p.key, e.target.value)}
                        placeholder={p.placeholder}
                      />
                      {p.hint && <span className="text-[10px] text-zinc-600">{p.hint}</span>}
                    </div>
                  ))}
                  <p className="text-[10px] text-zinc-600">
                    Değerlerde <span className="font-mono text-zinc-500">{"{{node-id.output}}"}</span> kullanabilirsiniz.
                  </p>
                </div>
              </Field>
            )}
          </>
        )}

        {/* ── Decision ── */}
        {node.type === "decision" && (
          <Field label="Koşullar">
            <div className="flex flex-col gap-3">
              {conditions.map((c, i) => (
                <div key={i} className="flex flex-col gap-1 rounded-lg border border-zinc-800 bg-zinc-900/40 p-2">
                  <div className="flex items-center gap-1.5">
                    <input
                      className={cn(inputCls, "flex-1 bg-zinc-900")}
                      value={c.label}
                      onChange={(e) => {
                        const next = [...conditions];
                        next[i] = {
                          ...next[i],
                          label: e.target.value,
                          handle: e.target.value.toLowerCase().replace(/\s+/g, "_"),
                        };
                        set("conditions", next);
                      }}
                      placeholder={`Etiket ${i + 1}`}
                    />
                    <button
                      onClick={() => set("conditions", conditions.filter((_, j) => j !== i))}
                      className="rounded p-1 text-zinc-600 hover:text-red-400"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                  <input
                    className={cn(inputCls, "bg-zinc-900 font-mono text-[11px]")}
                    value={c.condition ?? ""}
                    onChange={(e) => {
                      const next = [...conditions];
                      next[i] = { ...next[i], condition: e.target.value };
                      set("conditions", next);
                    }}
                    placeholder='{{node-id.output}} contains "metin"'
                  />
                </div>
              ))}
              <button
                onClick={() =>
                  set("conditions", [
                    ...conditions,
                    { handle: `secim_${conditions.length + 1}`, label: `Seçim ${conditions.length + 1}`, condition: "" },
                  ])
                }
                className="flex items-center gap-1.5 rounded-lg border border-dashed border-zinc-800 px-2.5 py-1.5 text-[11px] text-zinc-600 hover:border-zinc-700 hover:text-zinc-400"
              >
                <Plus size={11} /> Koşul ekle
              </button>
              <p className="text-[10px] text-zinc-600 leading-relaxed">
                Kural boşsa etiket adı son çıktıda aranır. Eşleşme yoksa LLM karar verir.
              </p>
            </div>
          </Field>
        )}

        {/* ── Loop ── */}
        {node.type === "loop" && (
          <>
            <Field label="Max tekrar">
              <input
                type="number"
                className={inputCls}
                value={(data.max_iterations as string) ?? "5"}
                onChange={(e) => set("max_iterations", e.target.value)}
                min={1}
              />
            </Field>
            <Field label="Çıkış koşulu">
              <input
                className={cn(inputCls, "font-mono text-[11px]")}
                value={(data.exit_condition as string) ?? ""}
                onChange={(e) => set("exit_condition", e.target.value)}
                placeholder='{{node-id.output}} contains "bitti"'
              />
              <p className="text-[10px] text-zinc-600">Boşsa max tekrar sayısına kadar çalışır.</p>
            </Field>
            <Field label="Gövde node&apos;ları">
              {candidateNodes.length === 0 ? (
                <p className="text-[11px] text-zinc-600">Canvas&apos;ta başka node yok.</p>
              ) : (
                <div className="flex flex-col gap-1 rounded-lg border border-zinc-800 bg-zinc-900 p-2">
                  {candidateNodes.map((n) => {
                    const checked = bodyNodeIds.includes(n.id);
                    return (
                      <label key={n.id} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-zinc-800/60">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) =>
                            set(
                              "body_node_ids",
                              e.target.checked
                                ? [...bodyNodeIds, n.id]
                                : bodyNodeIds.filter((id) => id !== n.id)
                            )
                          }
                          className="accent-indigo-500"
                        />
                        <span className="flex-1 text-[11px] text-zinc-300">
                          {(n.data?.label as string) || n.id}
                        </span>
                        <span className="text-[10px] text-zinc-600">{n.type}</span>
                      </label>
                    );
                  })}
                </div>
              )}
              <p className="text-[10px] text-zinc-600">Sıra önemlidir — seçim sırasına göre çalışır.</p>
            </Field>
          </>
        )}

        {/* Note (all types) */}
        <Field label="Not">
          <textarea
            className={textareaCls}
            rows={4}
            value={(data.note as string) ?? ""}
            onChange={(e) => set("note", e.target.value)}
            placeholder="Bu node ne yapacak? Orkestratör bu notu okur."
          />
        </Field>
      </div>

      {/* Save */}
      <div className="border-t border-zinc-800/80 p-4">
        <Button size="sm" className="w-full" onClick={save}>Uygula</Button>
      </div>
    </aside>
  );
}
