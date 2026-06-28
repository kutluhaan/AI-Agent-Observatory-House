"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api, ApiError, type WorkflowData } from "@/lib/api";
import { WorkflowCanvas, type GraphJson } from "@/components/workflow/canvas";

export default function NewWorkflowPage() {
  const router = useRouter();
  const [name, setName] = useState("Yeni Workflow");
  const [saving, setSaving] = useState(false);

  async function handleSave(graph: GraphJson) {
    setSaving(true);
    try {
      const wf = await api.post<WorkflowData>("/workflows", {
        name: name.trim() || "Yeni Workflow",
        graph_json: graph,
      });
      router.replace(`/workflows/${wf.id}`);
    } catch (err) {
      console.error(err instanceof ApiError ? err.message : err);
      setSaving(false);
    }
  }

  return (
    <div className="flex h-[calc(100dvh-48px)] flex-col">
      <WorkflowCanvas
        onSave={handleSave}
        saving={saving}
        topBar={
          <div className="flex items-center gap-3">
            <Link href="/workflows" className="text-zinc-600 hover:text-zinc-300">
              <ArrowLeft size={16} />
            </Link>
            <input
              className="rounded border border-transparent bg-transparent px-1 py-0.5 text-sm font-medium text-zinc-100 focus:border-zinc-700 focus:bg-zinc-900 focus:outline-none"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Workflow adı"
            />
          </div>
        }
      />
    </div>
  );
}
