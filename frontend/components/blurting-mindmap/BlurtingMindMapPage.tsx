"use client";

import { useState } from "react";
import BlurtingBoard from "./BlurtingBoard";
import MindMapBoard from "./MindMapBoard";
import styles from "./BlurtingMindMap.module.css";

type Mode = "blurting" | "mindmap";

export default function BlurtingMindMapPage() {
  const [mode, setMode] = useState<Mode>("blurting");

  return (
    <div className={styles.pageShell}>
      <section className={styles.hero}>
        <div className={styles.heroGlowPink} />
        <div className={styles.heroGlowGreen} />
        <div className={styles.heroGlowYellow} />

        <div className={styles.heroContent}>
          <div className={styles.heroBadge}>Active Recall Studio</div>

          <h1 className={styles.heroTitle}>Blurting / Mind Map</h1>

          <p className={styles.heroSubtitle}>
            Dump what you know fast, or build concept links visually. This page
            is fully manual and memory-driven — no extracted concepts, no
            autofill, just your own recall.
          </p>

          <div className={styles.modeTabs} role="tablist" aria-label="Study mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "blurting"}
              className={`${styles.modeTab} ${
                mode === "blurting" ? styles.modeTabActive : ""
              }`}
              onClick={() => setMode("blurting")}
            >
              Blurting
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={mode === "mindmap"}
              className={`${styles.modeTab} ${
                mode === "mindmap" ? styles.modeTabActive : ""
              }`}
              onClick={() => setMode("mindmap")}
            >
              Mind Map
            </button>
          </div>
        </div>
      </section>

      <section className={styles.contentSection}>
        {mode === "blurting" ? <BlurtingBoard /> : <MindMapBoard />}
      </section>
    </div>
  );
}