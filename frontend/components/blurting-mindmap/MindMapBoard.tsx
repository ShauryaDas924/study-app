"use client";
import {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  NodeChange,
  EdgeChange,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
  useReactFlow,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import MindMapNode, { MindMapNodeData } from "./MindMapNode";
import styles from "./BlurtingMindMap.module.css";
import { useStore } from "@/store/useStore";
type Tool = "select" | "rectangle" | "circle" | "text" | "pill" | "diamond";

type CustomNode = Node<MindMapNodeData>;
type MindMapStorage = {
  nodes: CustomNode[];
  edges: Edge[];
};
const nodeTypes = {
  mindNode: MindMapNode,
};

function MindMapCanvas() {
  const reactFlow = useReactFlow<CustomNode, Edge>();
const classId = useStore((s) => s.selectedClassId);
  const [tool, setTool] = useState<Tool>("select");
  const [nodes, setNodes] = useState<CustomNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

 const attachCallbacks = useCallback(
  (nodesToWrap: CustomNode[]) =>
    nodesToWrap.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onChangeLabel: (id: string, nextValue: string) => {
          setNodes((current) =>
            current.map((item) =>
              item.id === id
                ? {
                    ...item,
                    data: {
                      ...item.data,
                      label: nextValue,
                    },
                  }
                : item
            )
          );
        },
        onResizeNode: (
          id: string,
          direction: "wider" | "narrower" | "taller" | "shorter"
        ) => {
          setNodes((current) =>
            current.map((item) => {
              if (item.id !== id) return item;

              const currentWidth = item.data.width ?? 180;
              const currentHeight = item.data.height ?? 80;

              const nextWidth =
                direction === "wider"
                  ? Math.min(currentWidth + 20, 320)
                  : direction === "narrower"
                  ? Math.max(currentWidth - 20, 100)
                  : currentWidth;

              const nextHeight =
                direction === "taller"
                  ? Math.min(currentHeight + 20, 240)
                  : direction === "shorter"
                  ? Math.max(currentHeight - 20, 56)
                  : currentHeight;

              return {
                ...item,
                data: {
                  ...item.data,
                  width: nextWidth,
                  height: nextHeight,
                },
              };
            })
          );
        },
      },
    })),
  []
);
useEffect(() => {
  if (!classId) return;

  const saved = localStorage.getItem(`mindmap_board_${classId}`);
  if (!saved) return;

  try {
    const parsed: MindMapStorage = JSON.parse(saved);
    const restoredNodes = attachCallbacks(parsed.nodes ?? []);
    setNodes(restoredNodes);
    setEdges(parsed.edges ?? []);
  } catch (error) {
    console.error("Failed to load mind map from localStorage", error);
  }
}, [classId, attachCallbacks]);

useEffect(() => {
  if (!classId) return;

  const payload: MindMapStorage = {
    nodes: nodes.map((node) => ({
      ...node,
      data: {
  ...node.data,
  onChangeLabel: undefined as never,
  onResizeNode: undefined as never,
},
    })),
    edges,
  };

  localStorage.setItem(`mindmap_board_${classId}`, JSON.stringify(payload));
}, [classId, nodes, edges]);

  const onNodesChange = useCallback((changes: NodeChange<CustomNode>[]) => {
    setNodes((current) => attachCallbacks(applyNodeChanges(changes, current)));
  }, [attachCallbacks]);

  const onEdgesChange = useCallback((changes: EdgeChange<Edge>[]) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) =>
      addEdge(
        {
          ...connection,
          animated: true,
          style: { strokeWidth: 2.5, stroke: "#5e6b61" },
        },
        current
      )
    );
  }, []);

 const makeNode = useCallback(
  (
    variant: "rectangle" | "circle" | "text" | "pill" | "diamond",
    x: number,
    y: number
  ): CustomNode => {
    const defaultLabel =
      variant === "rectangle"
        ? "Main concept"
        : variant === "circle"
        ? "Linked idea"
        : variant === "pill"
        ? "Key point"
        : variant === "diamond"
        ? "Decision / event"
        : "Short label";

    const defaultWidth =
      variant === "circle" ? 150 :
      variant === "text" ? 170 :
      variant === "pill" ? 200 :
      variant === "diamond" ? 150 :
      190;

    const defaultHeight =
      variant === "circle" ? 150 :
      variant === "text" ? 64 :
      variant === "pill" ? 84 :
      variant === "diamond" ? 150 :
      86;

    return {
      id: `${variant}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type: "mindNode",
      position: { x, y },
      data: {
        label: defaultLabel,
        variant,
        width: defaultWidth,
        height: defaultHeight,
        onChangeLabel: () => {},
        onResizeNode: () => {},
      },
    };
  },
  []
);

 const addNodeAtCenter = useCallback(
  (variant: "rectangle" | "circle" | "text" | "pill" | "diamond") => {
      const node = makeNode(variant, 220 + Math.random() * 160, 160 + Math.random() * 140);
      setNodes((current) => attachCallbacks([...current, node]));
      setTool("select");
    },
    [attachCallbacks, makeNode]
  );

  const onPaneClick = useCallback(
    (event: React.MouseEvent) => {
      if (tool === "select") return;

      const variant =
  tool === "rectangle"
    ? "rectangle"
    : tool === "circle"
    ? "circle"
    : tool === "pill"
    ? "pill"
    : tool === "diamond"
    ? "diamond"
    : "text";

      const position = reactFlow.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const node = makeNode(variant, position.x - 80, position.y - 30);
      setNodes((current) => attachCallbacks([...current, node]));
      setTool("select");
    },
    [attachCallbacks, makeNode, reactFlow, tool]
  );

  const deleteSelection = useCallback(() => {
    const selectedNodeIds = new Set(nodes.filter((n) => n.selected).map((n) => n.id));
    const selectedEdgeIds = new Set(edges.filter((e) => e.selected).map((e) => e.id));

    if (selectedNodeIds.size === 0 && selectedEdgeIds.size === 0) return;

    setNodes((current) => current.filter((n) => !selectedNodeIds.has(n.id)));
    setEdges((current) =>
      current.filter(
        (e) =>
          !selectedEdgeIds.has(e.id) &&
          !selectedNodeIds.has(e.source) &&
          !selectedNodeIds.has(e.target)
      )
    );
  }, [edges, nodes]);

  const clearCanvas = useCallback(() => {
  setNodes([]);
  setEdges([]);
  setTool("select");

  if (classId) {
    localStorage.removeItem(`mindmap_board_${classId}`);
  }
}, [classId]);

  const helperText = useMemo(() => {
  if (tool === "rectangle") return "Click the canvas to place a rectangle node.";
  if (tool === "circle") return "Click the canvas to place a circle node.";
  if (tool === "pill") return "Click the canvas to place a pill node.";
  if (tool === "diamond") return "Click the canvas to place a diamond node.";
  if (tool === "text") return "Click the canvas to place a text label node.";
  return "Select/move nodes, then drag handles to create connectors. Select a node to resize it.";
}, [tool]);
if (!classId) {
  return (
    <div className={styles.panelWrap}>
      <div className={styles.panelTitle}>Mind Map Board</div>
      <p className={styles.panelText}>
        Select a course first to save mind maps by class.
      </p>
    </div>
  );
}
  return (
    <div className={styles.panelWrap}>
      <div className={styles.panelTopRow}>
        <div className={styles.panelIntro}>
          <h2 className={styles.panelTitle}>Mind Map Board</h2>
          <p className={styles.panelText}>
            Build concepts visually. Add nodes, move them around, and connect
            them with lines.
          </p>
        </div>

        <div className={styles.blurtingStatus}>
          <span className={styles.statusChip}>
            {nodes.length} nodes
          </span>
          <span className={styles.statusChip}>
            {edges.length} links
          </span>
        </div>
      </div>

      <div className={styles.mindMapShell}>
        <div className={styles.mindMapToolbar}>
          <button
            type="button"
            className={`${styles.toolButton} ${tool === "select" ? styles.toolButtonActive : ""}`}
            onClick={() => setTool("select")}
          >
            Select / Move
          </button>

          <button
            type="button"
            className={`${styles.toolButton} ${tool === "rectangle" ? styles.toolButtonActive : ""}`}
            onClick={() => setTool("rectangle")}
          >
            Rectangle Node
          </button>

          <button
            type="button"
            className={`${styles.toolButton} ${tool === "circle" ? styles.toolButtonActive : ""}`}
            onClick={() => setTool("circle")}
          >
            Circle Node
          </button>
<button
  type="button"
  className={`${styles.toolButton} ${tool === "pill" ? styles.toolButtonActive : ""}`}
  onClick={() => setTool("pill")}
>
  Pill Node
</button>

<button
  type="button"
  className={`${styles.toolButton} ${tool === "diamond" ? styles.toolButtonActive : ""}`}
  onClick={() => setTool("diamond")}
>
  Diamond Node
</button>
          <button
            type="button"
            className={`${styles.toolButton} ${tool === "text" ? styles.toolButtonActive : ""}`}
            onClick={() => setTool("text")}
          >
            Text Label
          </button>

          <button
            type="button"
            className={styles.toolButton}
            onClick={() => addNodeAtCenter("rectangle")}
          >
            Quick Add Rectangle
          </button>

          <button
            type="button"
            className={styles.toolButton}
            onClick={() => addNodeAtCenter("circle")}
          >
            Quick Add Circle
          </button>

<button
  type="button"
  className={styles.toolButton}
  onClick={() => addNodeAtCenter("pill")}
>
  Quick Add Pill
</button>

<button
  type="button"
  className={styles.toolButton}
  onClick={() => addNodeAtCenter("diamond")}
>
  Quick Add Diamond
</button>


          <button
            type="button"
            className={styles.toolButton}
            onClick={() => addNodeAtCenter("text")}
          >
            Quick Add Text
          </button>

          <button
            type="button"
            className={styles.toolButtonDanger}
            onClick={deleteSelection}
          >
            Delete Selected
          </button>

          <button
            type="button"
            className={styles.toolButtonDanger}
            onClick={clearCanvas}
          >
            Clear Canvas
          </button>

          <div className={styles.helperCard}>
            <div className={styles.helperCardTitle}>How to connect</div>
            <p className={styles.helperCardText}>
              Select/move mode is for dragging nodes. To connect ideas, drag
              from one node handle to another.
            </p>
          </div>

          <div className={styles.helperHint}>{helperText}</div>
        </div>

        <div className={styles.flowCanvasWrap}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onPaneClick={onPaneClick}
            fitView
            deleteKeyCode={["Backspace", "Delete"]}
            className={styles.flowCanvas}
            defaultEdgeOptions={{
              animated: true,
              style: { strokeWidth: 2.5, stroke: "#5e6b61" },
            }}
          >
            <Panel position="top-center">
              <div className={styles.flowPanelBanner}>
                {helperText}
              </div>
            </Panel>

            <MiniMap
              pannable
              zoomable
              className={styles.miniMap}
              nodeStrokeWidth={3}
            />
            <Controls />
            <Background gap={18} size={1.4} />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}

export default function MindMapBoard() {
  return (
    <ReactFlowProvider>
      <MindMapCanvas />
    </ReactFlowProvider>
  );
}