"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  RefreshCw,
  Folder,
  FolderOpen,
  FileText,
  Download,
  ChevronRight,
  ChevronDown,
  Eye,
  Code2,
} from "lucide-react";
import { api, type Agent, type AgentFile } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";

function isMarkdownPath(path: string): boolean {
  return /\.(md|markdown|mdx)$/i.test(path);
}

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  size?: number;
  children: TreeNode[];
}

function buildTree(files: AgentFile[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", isDir: true, children: [] };
  const dirs = new Map<string, TreeNode>([["", root]]);

  function ensureDir(path: string): TreeNode {
    const existing = dirs.get(path);
    if (existing) return existing;
    const parts = path.split("/");
    const parent = ensureDir(parts.slice(0, -1).join("/"));
    const node: TreeNode = { name: parts[parts.length - 1], path, isDir: true, children: [] };
    parent.children.push(node);
    dirs.set(path, node);
    return node;
  }

  for (const f of files) {
    const parts = f.path.split("/");
    const parentPath = parts.slice(0, -1).join("/");
    const parent = ensureDir(parentPath);
    if (f.is_dir) {
      ensureDir(f.path);
    } else {
      parent.children.push({
        name: parts[parts.length - 1],
        path: f.path,
        isDir: false,
        size: f.size_bytes,
        children: [],
      });
    }
  }

  function sortNode(n: TreeNode) {
    n.children.sort((a, b) =>
      a.isDir !== b.isDir ? (a.isDir ? -1 : 1) : a.name.localeCompare(b.name),
    );
    n.children.forEach(sortNode);
  }
  sortNode(root);
  return root.children;
}

export default function AgentFilesPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [files, setFiles] = useState<AgentFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openFile, setOpenFile] = useState<{ path: string; content: string } | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [rawView, setRawView] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<AgentFile[]>(`/agents/${id}/files`)
      .then(setFiles)
      .catch(() => setError("Dosyalar yüklenemedi."))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    api.get<Agent>(`/agents/${id}`).then(setAgent).catch(() => {});
    load();
  }, [id, load]);

  async function openPath(path: string) {
    setViewerLoading(true);
    setRawView(false);
    try {
      const f = await api.get<{ path: string; content: string }>(
        `/agents/${id}/files/content?path=${encodeURIComponent(path)}`,
      );
      setOpenFile({ path: f.path, content: f.content });
    } catch {
      setOpenFile({ path, content: "[Dosya okunamadı]" });
    } finally {
      setViewerLoading(false);
    }
  }

  function download() {
    if (!openFile) return;
    const blob = new Blob([openFile.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = openFile.path.split("/").pop() ?? "file.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  const tree = buildTree(files);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <Link
        href={`/agents/${id}/chat`}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Sohbete dön
      </Link>

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Dosyalar</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {agent?.name ?? "…"} — izole dosya sistemi (salt-okunur)
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
        >
          <RefreshCw size={12} />
          Yenile
        </button>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-[260px_1fr]">
        {/* Ağaç */}
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-2">
          {loading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-4 w-4" />
            </div>
          ) : tree.length === 0 ? (
            <p className="py-8 text-center text-xs text-zinc-600">Henüz dosya yok</p>
          ) : (
            <div className="flex flex-col">
              {tree.map((n) => (
                <TreeView
                  key={n.path}
                  node={n}
                  depth={0}
                  activePath={openFile?.path ?? null}
                  onOpen={openPath}
                />
              ))}
            </div>
          )}
        </div>

        {/* Görüntüleyici */}
        <div className="min-h-[300px] rounded-xl border border-zinc-800/80 bg-zinc-950/40">
          {viewerLoading ? (
            <div className="flex justify-center py-16">
              <Spinner className="h-4 w-4" />
            </div>
          ) : openFile ? (
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5">
                <span className="truncate font-mono text-xs text-zinc-300">{openFile.path}</span>
                <div className="flex shrink-0 items-center gap-1.5">
                  {isMarkdownPath(openFile.path) && (
                    <button
                      onClick={() => setRawView((r) => !r)}
                      className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
                      title={rawView ? "Önizleme" : "Ham metin"}
                    >
                      {rawView ? <Eye size={11} /> : <Code2 size={11} />}
                      {rawView ? "Önizleme" : "Ham"}
                    </button>
                  )}
                  <button
                    onClick={download}
                    className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
                  >
                    <Download size={11} />
                    İndir
                  </button>
                </div>
              </div>
              {isMarkdownPath(openFile.path) && !rawView ? (
                <div className="flex-1 overflow-auto p-4">
                  {openFile.content ? (
                    <Markdown>{openFile.content}</Markdown>
                  ) : (
                    <span className="text-xs text-zinc-600">(boş dosya)</span>
                  )}
                </div>
              ) : (
                <pre className="flex-1 overflow-auto whitespace-pre-wrap p-4 text-xs text-zinc-300">
                  {openFile.content || "(boş dosya)"}
                </pre>
              )}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center py-16 text-xs text-zinc-600">
              Görüntülemek için bir dosya seç
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TreeView({
  node,
  depth,
  activePath,
  onOpen,
}: {
  node: TreeNode;
  depth: number;
  activePath: string | null;
  onOpen: (path: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const pad = { paddingLeft: `${depth * 14 + 6}px` };

  if (node.isDir) {
    return (
      <div>
        <button
          onClick={() => setOpen((o) => !o)}
          style={pad}
          className="flex w-full items-center gap-1.5 rounded-md py-1.5 pr-2 text-left text-xs text-zinc-300 transition-colors hover:bg-zinc-900/60"
        >
          {open ? <ChevronDown size={12} className="text-zinc-600" /> : <ChevronRight size={12} className="text-zinc-600" />}
          {open ? <FolderOpen size={13} className="text-amber-400/80" /> : <Folder size={13} className="text-amber-400/80" />}
          <span className="truncate">{node.name}</span>
        </button>
        {open &&
          node.children.map((c) => (
            <TreeView key={c.path} node={c} depth={depth + 1} activePath={activePath} onOpen={onOpen} />
          ))}
      </div>
    );
  }

  return (
    <button
      onClick={() => onOpen(node.path)}
      style={pad}
      className={cn(
        "flex w-full items-center gap-1.5 rounded-md py-1.5 pr-2 text-left text-xs transition-colors",
        activePath === node.path ? "bg-indigo-500/10 text-indigo-200" : "text-zinc-400 hover:bg-zinc-900/60",
      )}
    >
      <span className="w-3" />
      <FileText size={13} className="shrink-0 text-zinc-500" />
      <span className="flex-1 truncate">{node.name}</span>
      {node.size != null && <span className="shrink-0 text-[10px] text-zinc-700">{node.size}b</span>}
    </button>
  );
}
