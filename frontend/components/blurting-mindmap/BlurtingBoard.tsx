"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./BlurtingMindMap.module.css";
import { useStore } from "@/store/useStore";
type BubbleTone = "pink" | "green" | "yellow";

type BubbleItem = {
  id: string;
  text: string;
  x: number;
  y: number;
  size: number;
  tone: BubbleTone;
  floatDuration: number;
  driftDuration: number;
  delay: number;
  rotate: number;
};
type BlurtingStorage = {
  duration: number;
  remainingTime: number;
  bubbles: BubbleItem[];
};
const TIMER_OPTIONS = [
  { label: "1 min", value: 60 },
  { label: "3 min", value: 180 },
  { label: "5 min", value: 300 },
];

function formatTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function randomTone(): BubbleTone {
  const tones: BubbleTone[] = ["pink", "green", "yellow"];
  return tones[Math.floor(Math.random() * tones.length)];
}

export default function BlurtingBoard() {
  const boardRef = useRef<HTMLDivElement | null>(null);
const classId = useStore((s) => s.selectedClassId);
  const [duration, setDuration] = useState<number>(60);
  const [remainingTime, setRemainingTime] = useState<number>(60);
  const [isRunning, setIsRunning] = useState(false);
  const [timeUp, setTimeUp] = useState(false);
  const [input, setInput] = useState("");
  const [bubbles, setBubbles] = useState<BubbleItem[]>([]);
useEffect(() => {
  if (!classId) return;

  const saved = localStorage.getItem(`blurting_board_${classId}`);
  if (!saved) return;

  try {
    const parsed: BlurtingStorage = JSON.parse(saved);
    setDuration(parsed.duration ?? 60);
    setRemainingTime(parsed.remainingTime ?? parsed.duration ?? 60);
    setBubbles(parsed.bubbles ?? []);
    setTimeUp(false);
    setIsRunning(false);
  } catch (error) {
    console.error("Failed to load blurting board from localStorage", error);
  }
}, [classId]);

useEffect(() => {
  if (!classId) return;

  const payload: BlurtingStorage = {
    duration,
    remainingTime,
    bubbles,
  };

  localStorage.setItem(`blurting_board_${classId}`, JSON.stringify(payload));
}, [classId, duration, remainingTime, bubbles]);
useEffect(() => {
  if (!isRunning) {
    setRemainingTime(duration);
  }
}, [duration, isRunning]);
  useEffect(() => {
    if (!isRunning) return;

    const timer = window.setInterval(() => {
      setRemainingTime((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer);
          setIsRunning(false);
          setTimeUp(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isRunning]);

  const bubbleCountLabel = useMemo(() => {
    if (bubbles.length === 1) return "1 bubble";
    return `${bubbles.length} bubbles`;
  }, [bubbles.length]);

  const startTimer = () => {
    setRemainingTime(duration);
    setTimeUp(false);
    setIsRunning(true);
  };

  const resetTimer = () => {
    setIsRunning(false);
    setTimeUp(false);
    setRemainingTime(duration);
  };

  const clearAll = () => {
  setBubbles([]);
  setInput("");
  setTimeUp(false);
  setIsRunning(false);
  setRemainingTime(duration);

  if (classId) {
    localStorage.removeItem(`blurting_board_${classId}`);
  }
};

  const createBubble = (text: string) => {
    const board = boardRef.current;
    const trimmed = text.trim();
    if (!trimmed) return;

    const width = board?.clientWidth ?? 1100;
    const height = board?.clientHeight ?? 620;

    const approximateWidth = clamp(trimmed.length * 8 + 80, 130, 280);
    const approximateHeight = 70;

    const x = clamp(
      Math.random() * (width - approximateWidth - 24) + 12,
      12,
      width - approximateWidth - 12
    );

    const y = clamp(
      Math.random() * (height - approximateHeight - 140) + 24,
      24,
      height - approximateHeight - 120
    );

    const nextBubble: BubbleItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      text: trimmed,
      x,
      y,
      size: clamp(0.94 + Math.random() * 0.22, 0.94, 1.16),
      tone: randomTone(),
      floatDuration: 4.8 + Math.random() * 2.8,
      driftDuration: 7.4 + Math.random() * 3.2,
      delay: Math.random() * 1.5,
      rotate: Math.random() * 8 - 4,
    };

    setBubbles((prev) => [...prev, nextBubble]);
    setInput("");
  };

  const handleSubmit = () => {
    createBubble(input);
  };
if (!classId) {
  return (
    <div className={styles.panelWrap}>
      <div className={styles.panelTitle}>Blurting Board</div>
      <p className={styles.panelText}>
        Select a course first to save blurting boards by class.
      </p>
    </div>
  );
}
  return (
    <div className={styles.panelWrap}>
      <div className={styles.panelTopRow}>
        <div className={styles.panelIntro}>
          <h2 className={styles.panelTitle}>Blurting Board</h2>
          <p className={styles.panelText}>
            Rapidly dump recall fragments into floating bubbles. Think in short
            pieces, not polished notes.
          </p>
        </div>

        <div className={styles.blurtingStatus}>
          <span className={styles.statusChip}>{bubbleCountLabel}</span>
          <span className={`${styles.statusChip} ${timeUp ? styles.statusChipAlert : ""}`}>
            {timeUp ? "Time is up" : isRunning ? "Session running" : "Ready"}
          </span>
        </div>
      </div>

      <div className={styles.controlsBar}>
        <div className={styles.timerGroup}>
          {TIMER_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`${styles.timerPill} ${
                duration === option.value ? styles.timerPillActive : ""
              }`}
              onClick={() => {
                setDuration(option.value);
                if (!isRunning) {
                  setRemainingTime(option.value);
                  setTimeUp(false);
                }
              }}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className={styles.timerReadoutWrap}>
          <div className={styles.timerReadout}>{formatTime(remainingTime)}</div>
          <div className={styles.timerActions}>
            <button type="button" className={styles.primaryAction} onClick={startTimer}>
              Start
            </button>
            <button type="button" className={styles.secondaryAction} onClick={resetTimer}>
              Reset Timer
            </button>
            <button type="button" className={styles.secondaryAction} onClick={clearAll}>
              Clear All
            </button>
          </div>
        </div>
      </div>

      <div ref={boardRef} className={styles.blurtingCanvas}>
        <div className={styles.canvasBackdropBlobPink} />
        <div className={styles.canvasBackdropBlobGreen} />
        <div className={styles.canvasBackdropBlobYellow} />

        {bubbles.length === 0 ? (
          <div className={styles.blurtingEmpty}>
            <div className={styles.blurtingEmptyTitle}>Start blurting</div>
            <p className={styles.blurtingEmptyText}>
              Type a fragment and press Enter. Each idea becomes a floating
              bubble.
            </p>
          </div>
        ) : null}

        {bubbles.map((bubble) => (
          <div
            key={bubble.id}
            className={`${styles.bubble} ${styles[`bubble${bubble.tone}`]}`}
            style={
              {
                left: `${bubble.x}px`,
                top: `${bubble.y}px`,
                transform: `scale(${bubble.size}) rotate(${bubble.rotate}deg)`,
                "--bubble-float-duration": `${bubble.floatDuration}s`,
                "--bubble-drift-duration": `${bubble.driftDuration}s`,
                "--bubble-delay": `${bubble.delay}s`,
              } as React.CSSProperties
            }
            title={bubble.text}
          >
            <span className={styles.bubbleText}>{bubble.text}</span>
          </div>
        ))}

        <div className={styles.blurtingInputDock}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Type one recall fragment and press Enter…"
            className={styles.blurtingInput}
          />

          <button
            type="button"
            className={styles.primaryAction}
            onClick={handleSubmit}
          >
            Add Bubble
          </button>
        </div>
      </div>
    </div>
  );
}