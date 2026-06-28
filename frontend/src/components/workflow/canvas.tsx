"use client";

import React, { useCallback, useRef, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Connection,
  type Node,
  type Edge,
} from "@xyflow/react";
import { nodeTypes } from "./nodes";
import { LeftPanel } from "./left-panel";
import { ConfigPanel } from "./config-panel";

export interface GraphJson {
  nodes: Node[];
  edges: Edge[];
}

interface WorkflowCanvasProps {
  initialGraph?: GraphJson | null;
  onSave: (graph: GraphJson) => Promise<void>;
  saving?: boolean;
  topBar: React.ReactNode;
  extraActions?: React.ReactNode;
}

let _nodeId = Date.now();
const nextId = (type: string) => `${type}-${++_nodeId}`;

function CanvasInner({ initialGraph, onSave, saving, topBar, extraActions }: WorkflowCanvasProps) {
  const { screenToFlowPosition } = useReactFlow();
  const canvasRef = useRef<HTMLDivElement>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialGraph?.nodes ?? []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialGraph?.edges ?? []);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const onConnect = useCallback(
    (conn: Connection) => setEdges((eds) => addEdge(conn, eds)),
    [setEdges]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData("application/reactflow");
      if (!raw) return;
      const { type, data } = JSON.parse(raw) as { type: string; data: Record<string, unknown> };
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      const newNode: Node = { id: nextId(type), type, position, data };
      setNodes((nds) => [...nds, newNode]);
    },
    [screenToFlowPosition, setNodes]
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const updateNodeData = useCallback((id: string, data: Record<string, unknown>) => {
    setNodes((nds) => nds.map((n) => (n.id === id ? { ...n, data } : n)));
  }, [setNodes]);

  const handleSave = () => {
    onSave({ nodes, edges });
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 bg-zinc-950 px-4 py-2">
        {topBar}
        <div className="flex items-center gap-2">
          {extraActions}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
          >
            {saving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        <LeftPanel />

        {/* Canvas */}
        <div ref={canvasRef} className="flex-1" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            deleteKeyCode="Delete"
            className="bg-zinc-950"
            defaultEdgeOptions={{ style: { stroke: "#6366f1", strokeWidth: 1.5 }, animated: false }}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#27272a" />
            <Controls className="!border-zinc-800 !bg-zinc-900 [&_button]:!border-zinc-800 [&_button]:!bg-zinc-900 [&_button]:!text-zinc-400 [&_button:hover]:!bg-zinc-800" />
            <MiniMap
              className="!border-zinc-800 !bg-zinc-900"
              nodeColor="#27272a"
              maskColor="rgba(9,9,11,0.7)"
            />
          </ReactFlow>
        </div>

        {/* Config panel */}
        {selectedNode && (
          <ConfigPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onUpdate={updateNodeData}
          />
        )}
      </div>
    </div>
  );
}

export function WorkflowCanvas(props: WorkflowCanvasProps) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}
