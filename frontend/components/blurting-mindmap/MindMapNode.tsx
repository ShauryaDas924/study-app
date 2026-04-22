"use client";

import { Handle, NodeProps, Position } from "@xyflow/react";
import styles from "./BlurtingMindMap.module.css";

export type MindMapVariant =
  | "rectangle"
  | "circle"
  | "text"
  | "pill"
  | "diamond";

export type MindMapNodeData = {
  label: string;
  variant: MindMapVariant;
  width?: number;
  height?: number;
  onChangeLabel: (id: string, nextValue: string) => void;
  onResizeNode: (id: string, direction: "wider" | "narrower" | "taller" | "shorter") => void;
};

export default function MindMapNode({ id, data, selected }: NodeProps) {
  const nodeData = data as MindMapNodeData;

  const className =
    nodeData.variant === "circle"
      ? styles.mindNodeCircle
      : nodeData.variant === "text"
      ? styles.mindNodeText
      : nodeData.variant === "pill"
      ? styles.mindNodePill
      : nodeData.variant === "diamond"
      ? styles.mindNodeDiamond
      : styles.mindNodeRectangle;

  const content =
    nodeData.variant === "diamond" ? (
      <div className={styles.mindNodeDiamondInner}>
        <input
          value={nodeData.label}
          onChange={(e) => nodeData.onChangeLabel(id, e.target.value)}
          className={styles.mindNodeInput}
          placeholder="Type here"
        />
      </div>
    ) : (
      <input
        value={nodeData.label}
        onChange={(e) => nodeData.onChangeLabel(id, e.target.value)}
        className={styles.mindNodeInput}
        placeholder="Type here"
      />
    );

  return (
    <div
      className={`${className} ${selected ? styles.mindNodeSelected : ""}`}
      style={{
        width: nodeData.width ? `${nodeData.width}px` : undefined,
        height: nodeData.height ? `${nodeData.height}px` : undefined,
      }}
    >
      <Handle type="target" position={Position.Top} className={styles.flowHandle} />
      <Handle type="target" position={Position.Left} className={styles.flowHandle} />
      <Handle type="source" position={Position.Right} className={styles.flowHandle} />
      <Handle type="source" position={Position.Bottom} className={styles.flowHandle} />

      {content}

      {selected && (
        <div className={styles.nodeResizeDock}>
          <button
            type="button"
            className={styles.nodeResizeButton}
            onClick={() => nodeData.onResizeNode(id, "wider")}
          >
            W+
          </button>
          <button
            type="button"
            className={styles.nodeResizeButton}
            onClick={() => nodeData.onResizeNode(id, "narrower")}
          >
            W-
          </button>
          <button
            type="button"
            className={styles.nodeResizeButton}
            onClick={() => nodeData.onResizeNode(id, "taller")}
          >
            H+
          </button>
          <button
            type="button"
            className={styles.nodeResizeButton}
            onClick={() => nodeData.onResizeNode(id, "shorter")}
          >
            H-
          </button>
        </div>
      )}
    </div>
  );
}