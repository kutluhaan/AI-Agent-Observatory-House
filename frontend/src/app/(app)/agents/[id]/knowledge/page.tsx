"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Plus,
  Pencil,
  Trash2,
  ScrollText,
  Scale,
  BookOpen,
  MessageSquareText,
  Sparkles,
  Power,
  ChevronRight,
} from "lucide-react";
import { Markdown } from "@/components/ui/markdown";
import {
  api,
  ApiError,
  type Agent,
  type AgentKnowledge,
  type KnowledgeKind,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { cn } from "@/lib/utils";

const KIND_META: Record<
  KnowledgeKind,
  { label: string; desc: string; alwaysOn: boolean; icon: typeof ScrollText }
> = {
  constitution: { label: "Anayasa", desc: "Temel ilkeler — her zaman aktif", alwaysOn: true, icon: ScrollText },
  rule: { label: "Kural", desc: "Uyulması gereken kurallar — her zaman aktif", alwaysOn: true, icon: Scale },
  instruction: { label: "Talimat", desc: "Nasıl davranılacağı — her zaman aktif", alwaysOn: true, icon: BookOpen },
  prompt: { label: "Ek prompt", desc: "System prompt'a eklenir — her zaman aktif", alwaysOn: true, icon: MessageSquareText },
  skill: { label: "Skill", desc: "Agent gerektiğinde okur — talep üzerine", alwaysOn: false, icon: Sparkles },
};

const KIND_ORDER: KnowledgeKind[] = ["constitution", "rule", "instruction", "prompt", "skill"];

/** İçerik markdown sözdizimi içeriyor mu? (başlık, kalın, liste, kod, link, alıntı, tablo) */
function looksLikeMarkdown(text: string): boolean {
  return /(^|\n)#{1,6}\s|\*\*[^*]+\*\*|(^|\n)\s*[-*+]\s|(^|\n)\s*\d+\.\s|```|\[[^\]]+\]\([^)]+\)|(^|\n)>\s|(^|\n)\|.*\|/.test(
    text,
  );
}

export default function AgentKnowledgePage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [items, setItems] = useState<AgentKnowledge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpand(itemId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  // Form / modal
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [fKind, setFKind] = useState<KnowledgeKind>("rule");
  const [fName, setFName] = useState("");
  const [fContent, setFContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<AgentKnowledge[]>(`/agents/${id}/knowledge`)
      .then(setItems)
      .catch(() => setError("Bilgi öğeleri yüklenemedi."))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    api.get<Agent>(`/agents/${id}`).then(setAgent).catch(() => {});
    load();
  }, [id, load]);

  function openAdd() {
    setEditingId(null);
    setFKind("rule");
    setFName("");
    setFContent("");
    setFormError("");
    setOpen(true);
  }

  function openEdit(item: AgentKnowledge) {
    setEditingId(item.id);
    setFKind(item.kind);
    setFName(item.name);
    setFContent(item.content);
    setFormError("");
    setOpen(true);
  }

  async function save() {
    if (!fName.trim() || !fContent.trim()) {
      setFormError("İsim ve içerik gerekli.");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      if (editingId) {
        await api.patch(`/agents/${id}/knowledge/${editingId}`, {
          name: fName.trim(),
          content: fContent,
        });
      } else {
        await api.post(`/agents/${id}/knowledge`, {
          kind: fKind,
          name: fName.trim(),
          content: fContent,
        });
      }
      setOpen(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: AgentKnowledge) {
    if (!window.confirm(`"${item.name}" öğesini silmek istediğine emin misin?`)) return;
    try {
      await api.delete(`/agents/${id}/knowledge/${item.id}`);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
    } catch {
      setError("Silinemedi.");
    }
  }

  async function toggleActive(item: AgentKnowledge) {
    try {
      const updated = await api.patch<AgentKnowledge>(`/agents/${id}/knowledge/${item.id}`, {
        is_active: !item.is_active,
      });
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
    } catch {
      setError("Güncellenemedi.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link
        href={`/agents/${id}/chat`}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Sohbete dön
      </Link>

      <div className="mb-2 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Knowledge Base</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {agent?.name ?? "…"} — kural, anayasa, talimat, prompt ve skill&apos;ler
          </p>
        </div>
        <Button size="sm" onClick={openAdd}>
          <Plus size={14} />
          Ekle
        </Button>
      </div>

      <p className="mb-6 mt-3 rounded-lg border border-zinc-800/70 bg-zinc-900/30 px-3.5 py-2.5 text-xs leading-relaxed text-zinc-500">
        <span className="text-zinc-300">Anayasa, kural, talimat ve ek prompt</span> her sohbette
        otomatik olarak agent&apos;ın sistem prompt&apos;una eklenir.{" "}
        <span className="text-zinc-300">Skill&apos;ler</span> ise agent ilgili bir görevde{" "}
        <code className="text-indigo-300">list_skills</code> /{" "}
        <code className="text-indigo-300">read_skill</code> ile talep üzerine okur.
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-14 text-center">
          <Sparkles size={26} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">Henüz bilgi öğesi yok.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Agent&apos;ın davranışını şekillendirmek için kural veya skill ekle.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {KIND_ORDER.map((kind) => {
            const group = items.filter((i) => i.kind === kind);
            if (group.length === 0) return null;
            const meta = KIND_META[kind];
            const Icon = meta.icon;
            return (
              <div key={kind}>
                <div className="mb-2 flex items-center gap-2">
                  <Icon size={14} className="text-indigo-400" />
                  <span className="text-sm font-medium text-zinc-200">{meta.label}</span>
                  <Badge variant={meta.alwaysOn ? "indigo" : "zinc"}>
                    {meta.alwaysOn ? "her zaman aktif" : "talep üzerine"}
                  </Badge>
                </div>
                <div className="flex flex-col gap-2">
                  {group.map((item) => {
                    const isOpen = expanded.has(item.id);
                    return (
                      <div
                        key={item.id}
                        className={cn(
                          "group rounded-lg border transition-colors",
                          item.is_active
                            ? "border-zinc-800/80 bg-zinc-900/40"
                            : "border-zinc-800/50 bg-zinc-900/20 opacity-60",
                        )}
                      >
                        <div className="flex items-center justify-between gap-3 px-3.5 py-2.5">
                          <button
                            onClick={() => toggleExpand(item.id)}
                            className="flex min-w-0 flex-1 items-center gap-2 text-left"
                          >
                            <ChevronRight
                              size={14}
                              className={cn(
                                "shrink-0 text-zinc-600 transition-transform",
                                isOpen && "rotate-90 text-zinc-400",
                              )}
                            />
                            <span className="truncate text-sm font-medium text-zinc-100">{item.name}</span>
                            {!isOpen && (
                              <span className="truncate text-xs text-zinc-600">
                                {item.content.replace(/\s+/g, " ").slice(0, 60)}
                              </span>
                            )}
                          </button>
                          <div
                            className={cn(
                              "flex shrink-0 items-center gap-0.5 transition-opacity",
                              isOpen ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                            )}
                          >
                            <button
                              onClick={() => toggleActive(item)}
                              title={item.is_active ? "Devre dışı bırak" : "Etkinleştir"}
                              className={cn(
                                "rounded-md p-1.5 transition-colors hover:bg-zinc-800",
                                item.is_active ? "text-emerald-400" : "text-zinc-600",
                              )}
                            >
                              <Power size={13} />
                            </button>
                            <button
                              onClick={() => openEdit(item)}
                              title="Düzenle"
                              className="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                            >
                              <Pencil size={13} />
                            </button>
                            <button
                              onClick={() => remove(item)}
                              title="Sil"
                              className="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-red-500/10 hover:text-red-400"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>
                        {isOpen && (
                          <div className="border-t border-zinc-800/60 px-3.5 py-3">
                            {looksLikeMarkdown(item.content) ? (
                              <Markdown>{item.content}</Markdown>
                            ) : (
                              <div className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
                                {item.content}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editingId ? "Knowledge Base öğesini düzenle" : "Knowledge Base öğesi ekle"}
        className="max-w-lg"
      >
        <div className="flex flex-col gap-4">
          {!editingId && (
            <Dropdown
              label="Tür"
              value={fKind}
              onChange={(v) => setFKind(v as KnowledgeKind)}
              options={KIND_ORDER.map((k) => ({
                value: k,
                label: KIND_META[k].label,
                hint: KIND_META[k].desc,
              }))}
            />
          )}
          <Input
            label="İsim"
            value={fName}
            onChange={(e) => setFName(e.target.value)}
            placeholder={fKind === "skill" ? "ör. deep-research" : "ör. Ton ve üslup"}
          />
          <Textarea
            label="İçerik"
            value={fContent}
            onChange={(e) => setFContent(e.target.value)}
            rows={8}
            placeholder={
              fKind === "skill"
                ? "Bu skill'in nasıl uygulanacağını adım adım yaz…"
                : "Agent'ın uyması gereken metni yaz…"
            }
          />
          {formError && <Alert variant="error">{formError}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              İptal
            </Button>
            <Button size="sm" onClick={save} disabled={saving}>
              {saving ? <Spinner className="h-3.5 w-3.5" /> : editingId ? "Kaydet" : "Ekle"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
