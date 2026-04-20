"use client";

import { Handle, NodeProps, Position } from "@xyflow/react";
import styles from "./BlurtingMindMap.module.css";

export type MindMapNodeData = {
  label: string;
  variant: "rectangle" | "circle" | "text";
  onChangeLabel: (id: string, nextValue: string) => void;
};

export default function MindMapNode({ id, data, selected }: NodeProps) {
  const nodeData = data as MindMapNodeData;

  const className =
    nodeData.variant === "circle"
      ? styles.mindNodeCircle
      : nodeData.variant === "text"
      ? styles.mindNodeText
      : styles.mindNodeRectangle;

  return (
    <div className={`${className} ${selected ? styles.mindNodeSelected : ""}`}>
      <Handle type="target" position={Position.Top} className={styles.flowHandle} />
      <Handle type="target" position={Position.Left} className={styles.flowHandle} />
      <Handle type="source" position={Position.Right} className={styles.flowHandle} />
      <Handle type="source" position={Position.Bottom} className={styles.flowHandle} />

      <input
        value={nodeData.label}
        onChange={(e) => nodeData.onChangeLabel(id, e.target.value)}
        className={styles.mindNodeInput}
        placeholder="Type here"
      />
    </div>
  );
}