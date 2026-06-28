"use client";

import React, { useEffect, useState } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { type Node } from "@xyflow/react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ConfigPanelProps {
  node: Node;
  onClose: () => void;
  onUpdate: (id: string, data: Record<string, unknown>) => void;
}

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

export function ConfigPanel({ node, onClose, onUpdate }: ConfigPanelProps) {
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
        {/* Label (all types except note) */}
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

        {/* Type-specific fields */}
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

        {node.type === "integration" && (
          <>
            <Field label="Servis">
              <select
                className={inputCls}
                value={(data.service as string) ?? "http"}
                onChange={(e) => set("service", e.target.value)}
              >
                <option value="gmail">Gmail</option>
                <option value="gcalendar">Google Calendar</option>
                <option value="gdrive">Google Drive</option>
                <option value="github">GitHub</option>
                <option value="db">Veritabanı</option>
                <option value="mcp">MCP Server</option>
                <option value="http">HTTP</option>
              </select>
            </Field>
            <Field label="Operasyon">
              <input
                className={inputCls}
                value={(data.operation as string) ?? ""}
                onChange={(e) => set("operation", e.target.value)}
                placeholder="ör. list_emails"
              />
            </Field>
          </>
        )}

        {node.type === "decision" && (
          <Field label="Koşullar">
            <div className="flex flex-col gap-2">
              {conditions.map((c, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <input
                    className={cn(inputCls, "flex-1")}
                    value={c.label}
                    onChange={(e) => {
                      const next = [...conditions];
                      next[i] = { ...next[i], label: e.target.value, handle: e.target.value.toLowerCase().replace(/\s+/g, "_") };
                      set("conditions", next);
                    }}
                    placeholder={`Koşul ${i + 1}`}
                  />
                  <button
                    onClick={() => set("conditions", conditions.filter((_, j) => j !== i))}
                    className="rounded p-1 text-zinc-600 hover:text-red-400"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
              <button
                onClick={() => set("conditions", [...conditions, { handle: `secim_${conditions.length + 1}`, label: `Seçim ${conditions.length + 1}` }])}
                className="flex items-center gap-1.5 rounded-lg border border-dashed border-zinc-800 px-2.5 py-1.5 text-[11px] text-zinc-600 hover:border-zinc-700 hover:text-zinc-400"
              >
                <Plus size={11} /> Koşul ekle
              </button>
            </div>
          </Field>
        )}

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
                className={inputCls}
                value={(data.exit_condition as string) ?? ""}
                onChange={(e) => set("exit_condition", e.target.value)}
                placeholder="ör. output.contains('tamamlandı')"
              />
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
