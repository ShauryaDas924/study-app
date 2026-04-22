"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "@/store/useStore";

type Card = {
  id: string;
  question: string;
  answer: string;
  confidence: number;
};

type ApiFlashcard = {
  id?: string | number;
  question: string;
  answer: string;
  confidence?: number;
};

type Mode =
  | "normal"
  | "hard"
  | "medium"
  | "speed"
  | "exam"
  | "streak"
  | "weakness"
  | "reverse"
  | "survival";

type SessionPayload = {
  cards: Card[];
  allCards: Card[];
  index: number;
  hardPile: Card[];
  mediumPile: Card[];
  mode: Mode;
};

type BackendSessionPayload = {
  index: number;
  mode: Mode;
  deck_ids: string[];
  all_deck_ids: string[];
  hard_ids: string[];
  medium_ids: string[];
};

function shuffle<T>(array: T[]): T[] {
  const arr = [...array];
  for (let j = arr.length - 1; j > 0; j--) {
    const k = Math.floor(Math.random() * (j + 1));
    [arr[j], arr[k]] = [arr[k], arr[j]];
  }
  return arr;
}

function saveSession(key: string, data: SessionPayload) {
  localStorage.setItem(key, JSON.stringify(data));
}

function loadSession(key: string): SessionPayload | null {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionPayload;
  } catch {
    return null;
  }
}

function reorderByIds(allCards: Card[], ids: string[]): Card[] {
  const map = new Map(allCards.map((c) => [c.id, c]));
  return ids.map((id) => map.get(id)).filter(Boolean) as Card[];
}

export default function FlashcardsPage() {
  const classId = useStore((s) => s.selectedClassId);
  const noteId = useStore((s) => s.selectedNoteId);
  const setSelectedNoteId = useStore((s) => s.setSelectedNoteId);

  const [notes, setNotes] = useState<any[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [i, setI] = useState(0);
  const [show, setShow] = useState(false);
  const [allCards, setAllCards] = useState<Card[]>([]);
  const [hardPile, setHardPile] = useState<Card[]>([]);
  const [mediumPile, setMediumPile] = useState<Card[]>([]);
  const [mode, setMode] = useState<Mode>("normal");

  const [streak, setStreak] = useState(0);
  const [bestStreak, setBestStreak] = useState(0);
  const [lives, setLives] = useState(3);
  const [speedTime, setSpeedTime] = useState(60);
  const [speedScore, setSpeedScore] = useState(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedDeckNoteId, setLoadedDeckNoteId] = useState<string | null>(null);
  const [isRestoringSession, setIsRestoringSession] = useState(false);

  const lastLoadedNoteId = useRef<string | undefined>(undefined);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const sessionKey = useMemo(() => {
    return noteId ? `flashcards_session_${noteId}` : "";
  }, [noteId]);

  useEffect(() => {
    if (!classId) return;

    let cancelled = false;

    async function loadNotes() {
      try {
        const res = await fetch(`http://localhost:8000/notes/by-class/${classId}`);
        const data = await res.json();
        if (cancelled) return;

        const arr = Array.isArray(data) ? data : [];
        setNotes(arr);

        if (arr.length && !noteId) {
          setSelectedNoteId(arr[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    }

    loadNotes();
    return () => {
      cancelled = true;
    };
  }, [classId, noteId, setSelectedNoteId]);

  useEffect(() => {
    if (!noteId) return;
    if (!cards.length) return;
    if (loadedDeckNoteId !== noteId) return;
    if (isRestoringSession) return;

    const payload = {
      index: i,
      mode,
      deck_ids: cards.map((c) => c.id),
      all_deck_ids: allCards.map((c) => c.id),
      hard_ids: hardPile.map((c) => c.id),
      medium_ids: mediumPile.map((c) => c.id),
    };

    fetch(`http://localhost:8000/notes/flashcards/session/${noteId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch((e) => {
      console.error("Failed to save backend session", e);
    });
  }, [
    noteId,
    loadedDeckNoteId,
    isRestoringSession,
    i,
    mode,
    cards,
    allCards,
    hardPile,
    mediumPile,
  ]);

  useEffect(() => {
    if (!classId || !noteId) return;
    if (!sessionKey) return;

    if (lastLoadedNoteId.current === noteId) return;
    lastLoadedNoteId.current = noteId;

    setLoadedDeckNoteId(null);
    setIsRestoringSession(true);

    void loadFreshDeck(noteId);
  }, [classId, noteId, sessionKey]);

  useEffect(() => {
    if (!noteId) return;
    if (!cards.length) return;

    saveSession(sessionKey, {
      cards,
      allCards,
      index: i,
      hardPile,
      mediumPile,
      mode,
    });
  }, [noteId, sessionKey, cards, allCards, i, hardPile, mediumPile, mode]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  async function loadFreshDeck(nid: string) {
    setLoading(true);
    setError(null);

    try {
      const [cardsRes, sessionRes] = await Promise.all([
        fetch(`http://localhost:8000/notes/flashcards/by-note/${nid}`),
        fetch(`http://localhost:8000/notes/flashcards/session/${nid}`),
      ]);

      if (!cardsRes.ok) {
        const t = await cardsRes.text();
        throw new Error(`Flashcards API error ${cardsRes.status}: ${t}`);
      }

      const cardsJson = (await cardsRes.json()) as unknown;
      const data: ApiFlashcard[] = Array.isArray(cardsJson) ? (cardsJson as ApiFlashcard[]) : [];

      const mapped: Card[] = data.map((c) => ({
        id: String(c.id ?? crypto.randomUUID()),
        question: String(c.question ?? ""),
        answer: String(c.answer ?? ""),
        confidence: Number(c.confidence ?? 0.5),
      }));

      let session: BackendSessionPayload | null = null;
      if (sessionRes.ok) {
        session = (await sessionRes.json()) as BackendSessionPayload;
      }

      if (session && Array.isArray(session.deck_ids) && session.deck_ids.length > 0) {
        const restoredAll =
          Array.isArray(session.all_deck_ids) && session.all_deck_ids.length > 0
            ? reorderByIds(mapped, session.all_deck_ids)
            : mapped;

        const restoredCards = reorderByIds(mapped, session.deck_ids);
        const restoredHard = reorderByIds(mapped, session.hard_ids ?? []);
        const restoredMedium = reorderByIds(mapped, session.medium_ids ?? []);

        const finalAllCards = restoredAll.length ? restoredAll : mapped;
        const finalCards = restoredCards.length ? restoredCards : shuffle(finalAllCards);
        const finalIndex = Math.min(session.index ?? 0, Math.max(finalCards.length - 1, 0));
        const finalMode: Mode = session.mode ?? "normal";

        setAllCards(finalAllCards);
        setCards(finalCards);
        setHardPile(restoredHard);
        setMediumPile(restoredMedium);
        setMode(finalMode);
        setI(finalIndex);
        setShow(false);
        setLoadedDeckNoteId(nid);
        setIsRestoringSession(false);

        saveSession(sessionKey, {
          cards: finalCards,
          allCards: finalAllCards,
          index: finalIndex,
          hardPile: restoredHard,
          mediumPile: restoredMedium,
          mode: finalMode,
        });

        return;
      }

      const saved = loadSession(sessionKey);
      if (saved && saved.cards?.length) {
        setAllCards(saved.allCards?.length ? saved.allCards : saved.cards);
        setCards(saved.cards);
        setI(Math.min(saved.index ?? 0, Math.max(saved.cards.length - 1, 0)));
        setHardPile(saved.hardPile ?? []);
        setMediumPile(saved.mediumPile ?? []);
        setMode(saved.mode ?? "normal");
        setShow(false);
        setLoadedDeckNoteId(nid);
        setIsRestoringSession(false);
        return;
      }

      const shuffled = shuffle(mapped);

      setAllCards(mapped);
      setCards(shuffled);
      setI(0);
      setShow(false);
      setHardPile([]);
      setMediumPile([]);
      setMode("normal");
      setLoadedDeckNoteId(nid);
      setIsRestoringSession(false);

      saveSession(sessionKey, {
        cards: shuffled,
        allCards: mapped,
        index: 0,
        hardPile: [],
        mediumPile: [],
        mode: "normal",
      });
    } catch (err: any) {
      console.error(err);
      setCards([]);
      setError(err?.message ?? "Failed to load flashcards");
      setLoadedDeckNoteId(null);
      setIsRestoringSession(false);
    } finally {
      setLoading(false);
    }
  }

  function reshuffleRemaining() {
    const remaining = cards.slice(i);
    const shuffled = shuffle(remaining);
    setCards([...cards.slice(0, i), ...shuffled]);
  }

  function startSpeedMode() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    setMode("speed");
    setCards((prev) => shuffle(prev));
    setSpeedScore(0);
    setSpeedTime(60);
    setI(0);
    setShow(false);

    timerRef.current = setInterval(() => {
      setSpeedTime((t) => {
        if (t <= 1) {
          if (timerRef.current) {
            clearInterval(timerRef.current);
          }
          alert("⚡ Speed round finished!");
          setMode("normal");
          return 0;
        }
        return t - 1;
      });
    }, 1000);
  }

  function startExamMode() {
    const examCards = shuffle([...cards]).slice(0, 25);
    setHardPile([]);
    setMediumPile([]);
    setCards(examCards);
    setI(0);
    setMode("exam");
    setShow(false);
  }

  function startWeaknessMode() {
    const weak = cards.filter((c) => c.confidence < 0.65);
    setCards(shuffle(weak));
    setMode("weakness");
    setI(0);
    setShow(false);
  }

  function startSurvivalMode() {
    setMode("survival");
    setLives(3);
    setI(0);
  }

  function returnToNormalMode() {
    setMode("normal");
    setCards(shuffle(allCards));
    setI(0);
    setShow(false);
    setStreak(0);
    setLives(3);
    setSpeedScore(0);
  }

  async function clearSession() {
    if (!sessionKey || !noteId) return;

    localStorage.removeItem(sessionKey);

    try {
      await fetch(`http://localhost:8000/notes/flashcards/session/${noteId}`, {
        method: "DELETE",
      });
    } catch (e) {
      console.error("Failed to clear backend session", e);
    }

    setAllCards([]);
    lastLoadedNoteId.current = undefined;
    void loadFreshDeck(noteId);
  }

  function finishSession() {
    alert("🎉 All reviews complete!");
    setMode("normal");
    setI(0);
    setShow(false);
  }

  function grade(level: "hard" | "medium" | "easy") {
    const current = cards[i];

    if (mode === "streak") {
      if (level === "easy") {
        const newStreak = streak + 1;
        setStreak(newStreak);
        setBestStreak(Math.max(bestStreak, newStreak));
      } else {
        setStreak(0);
      }
    }

    if (mode === "survival") {
      if (level !== "easy") {
        const newLives = lives - 1;
        setLives(newLives);

        if (newLives <= 0) {
          alert("💀 Game Over");
          setMode("normal");
          setLives(3);
          return;
        }
      }
    }

    if (mode === "speed" && level === "easy") {
      setSpeedScore((s) => s + 1);
    }

    if (level === "hard") setHardPile((p) => [...p, current]);
    if (level === "medium") setMediumPile((p) => [...p, current]);

    setShow(false);

    if (i + 1 < cards.length) {
      setI(i + 1);
      return;
    }

    if (mode === "normal") {
      const nextHard = level === "hard" ? [...hardPile, current] : hardPile;
      const nextMed = level === "medium" ? [...mediumPile, current] : mediumPile;

      if (nextHard.length) {
        setCards(shuffle(nextHard));
        setHardPile([]);
        setI(0);
        setMode("hard");
        return;
      }

      if (nextMed.length) {
        setCards(shuffle(nextMed));
        setMediumPile([]);
        setI(0);
        setMode("medium");
        return;
      }

      finishSession();
      return;
    }

    if (mode === "hard") {
      const nextMed = level === "medium" ? [...mediumPile, current] : mediumPile;
      if (nextMed.length) {
        setCards(shuffle(nextMed));
        setMediumPile([]);
        setI(0);
        setMode("medium");
        return;
      }
      finishSession();
      return;
    }

    finishSession();
  }

  function answerCard(result: "correct" | "wrong" | "skip") {
    if (mode === "speed" && result === "correct") {
      setSpeedScore((s) => s + 1);
    }

    if (mode === "streak") {
      if (result === "correct") {
        const newStreak = streak + 1;
        setStreak(newStreak);
        setBestStreak(Math.max(bestStreak, newStreak));
      } else {
        setStreak(0);
      }
    }

    if (mode === "survival" && result === "wrong") {
      const newLives = lives - 1;
      setLives(newLives);

      if (newLives <= 0) {
        alert("💀 Game Over");
        setMode("normal");
        setLives(3);
        return;
      }
    }

    setShow(false);

    if (i + 1 < cards.length) {
      setI(i + 1);
      return;
    }

    finishSession();
  }

  async function exportCSV() {
    if (!noteId) return;

    try {
      const res = await fetch(`http://localhost:8000/notes/flashcards/export-by-note/${noteId}`);
      if (!res.ok) {
        alert("Export failed");
        return;
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "flashcards.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("CSV export error:", err);
    }
  }

  if (!classId) {
    return (
      <div className="app-shell p-8">
        <div className="app-panel p-6">
          <div className="text-lg font-semibold" style={{ color: "var(--text-main)" }}>
            Select a class first.
          </div>
        </div>
      </div>
    );
  }

  if (!noteId) {
    return (
      <div className="app-shell p-8">
        <div className="app-panel p-6">
          <div className="text-lg font-semibold" style={{ color: "var(--text-main)" }}>
            Pick a note to study.
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="app-shell p-8">
        <div className="app-panel p-6">
          <div style={{ color: "var(--text-soft)" }}>Loading flashcards…</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-shell p-8 space-y-3">
        <div className="font-semibold" style={{ color: "var(--accent-pink-strong)" }}>
          Flashcards error
        </div>

        <pre
          className="text-xs p-3 rounded-2xl border"
          style={{
            background: "rgba(255,255,255,0.74)",
            borderColor: "var(--border-soft)",
            color: "var(--text-main)",
          }}
        >
          {error}
        </pre>

        <button
          onClick={() => loadFreshDeck(noteId)}
          className="app-button-primary px-3 py-2"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!cards.length) {
    return (
      <div className="app-shell p-8 space-y-4">
        <div className="app-panel p-6 space-y-4">
          <div style={{ color: "var(--text-main)" }}>No flashcards yet 📭</div>

          <select
            value={noteId}
            onChange={(e) => {
              lastLoadedNoteId.current = undefined;
              setSelectedNoteId(e.target.value);
            }}
            className="app-input px-3 py-2"
          >
            {notes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
          </select>

          <button
            onClick={() => loadFreshDeck(noteId)}
            className="app-button-primary px-3 py-2"
          >
            Refresh
          </button>
        </div>
      </div>
    );
  }

  const c = cards[Math.min(i, cards.length - 1)];
  const isGameMode =
    mode === "speed" ||
    mode === "streak" ||
    mode === "survival" ||
    mode === "exam";

  return (
    <div className="app-shell p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-semibold" style={{ color: "var(--text-main)" }}>
          Flashcard Study
        </h1>
        <p className="mt-2" style={{ color: "var(--text-soft)" }}>
          Study with a softer, focused flow. Switch modes, review intelligently, and keep momentum.
        </p>
      </div>

      <div className="app-panel p-4">
        <select
          value={noteId}
          onChange={(e) => {
            lastLoadedNoteId.current = undefined;
            setSelectedNoteId(e.target.value);
          }}
          className="app-input px-3 py-2"
        >
          {notes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.title}
            </option>
          ))}
        </select>
      </div>

      <div className="flex gap-3 flex-wrap text-sm">
        {mode === "streak" && (
          <div
            className="px-3 py-2 rounded-full border"
            style={{
              background: "linear-gradient(135deg, #fff0d9 0%, #ffe0a8 100%)",
              borderColor: "var(--border-soft)",
              color: "#8b5b10",
            }}
          >
            🔥 Streak: {streak} | Best: {bestStreak}
          </div>
        )}

        {mode === "survival" && (
          <div
            className="px-3 py-2 rounded-full border"
            style={{
              background: "linear-gradient(135deg, #ffe5ec 0%, #ffd7e2 100%)",
              borderColor: "var(--border-soft)",
              color: "#8a4456",
            }}
          >
            Lives: {"❤️".repeat(lives)}
          </div>
        )}

        {mode === "speed" && (
          <div
            className="px-3 py-2 rounded-full border"
            style={{
              background: "var(--gradient-main)",
              borderColor: "var(--border-soft)",
              color: "var(--text-main)",
            }}
          >
            ⏱ {speedTime}s | Score: {speedScore}
          </div>
        )}

        <button
          disabled={!hardPile.length}
          onClick={() => {
            setCards(shuffle(hardPile));
            setHardPile([]);
            setI(0);
            setMode("hard");
            setShow(false);
          }}
          className="px-3 py-2 rounded-full border disabled:opacity-50"
          style={{
            background: "linear-gradient(135deg, #ffe4ea 0%, #fff0d9 100%)",
            borderColor: "var(--border-soft)",
            color: "#7a4551",
          }}
        >
          Hard: {hardPile.length}
        </button>

        <button
          disabled={!mediumPile.length}
          onClick={() => {
            setCards(shuffle(mediumPile));
            setMediumPile([]);
            setI(0);
            setMode("medium");
            setShow(false);
          }}
          className="px-3 py-2 rounded-full border disabled:opacity-50"
          style={{
            background: "linear-gradient(135deg, #fff6de 0%, #eef7ec 100%)",
            borderColor: "var(--border-soft)",
            color: "#6d5d18",
          }}
        >
          Medium: {mediumPile.length}
        </button>

        <div
          className="px-3 py-2 rounded-full border"
          style={{
            background: "rgba(255,255,255,0.7)",
            borderColor: "var(--border-soft)",
            color: "var(--text-soft)",
          }}
        >
          Mode: {mode}
        </div>
      </div>

      <div className="flex gap-3 flex-wrap">
        <button onClick={returnToNormalMode} className="app-button-secondary px-3 py-2 text-sm">
          🏠 Normal
        </button>

        <button onClick={reshuffleRemaining} className="app-button-primary px-3 py-2 text-sm">
          🔀 Shuffle
        </button>

        <button onClick={clearSession} className="app-button-secondary px-3 py-2 text-sm">
          ♻️ Reset
        </button>

        <button onClick={startSpeedMode} className="app-button-primary px-3 py-2 text-sm">
          ⚡ Speed
        </button>

        <button onClick={startExamMode} className="app-button-primary px-3 py-2 text-sm">
          📝 Exam
        </button>

        <button
          onClick={() => setMode("streak")}
          className="px-3 py-2 rounded-xl text-sm border"
          style={{
            background: "linear-gradient(135deg, #fff0d9 0%, #ffe1a7 100%)",
            borderColor: "var(--border-soft)",
            color: "#8b5b10",
          }}
        >
          🔥 Streak
        </button>

        <button
          onClick={() => setMode("reverse")}
          className="px-3 py-2 rounded-xl text-sm border"
          style={{
            background: "linear-gradient(135deg, #e7faf4 0%, #d8f0e2 100%)",
            borderColor: "var(--border-soft)",
            color: "#2f6f63",
          }}
        >
          🔄 Reverse
        </button>

        <button
          onClick={startWeaknessMode}
          className="px-3 py-2 rounded-xl text-sm border"
          style={{
            background: "linear-gradient(135deg, #ffe7ee 0%, #ffd8e3 100%)",
            borderColor: "var(--border-soft)",
            color: "#894353",
          }}
        >
          🧠 Weakness
        </button>

        <button
          onClick={startSurvivalMode}
          className="px-3 py-2 rounded-xl text-sm border"
          style={{
            background: "linear-gradient(135deg, #f2f2f2 0%, #d9d9d9 100%)",
            borderColor: "var(--border-soft)",
            color: "#2f2a2f",
          }}
        >
          💀 Survival
        </button>

        <button onClick={exportCSV} className="app-button-secondary px-3 py-2 text-sm">
          ⬇️ Export CSV
        </button>
      </div>

      <div
        className="relative border rounded-[28px] p-8"
        style={{
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(255,248,252,0.96) 52%, rgba(248,255,247,0.96) 100%)",
          borderColor: "var(--border-soft)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div
          className="absolute top-4 right-4 text-xs px-3 py-1.5 rounded-full border"
          style={{
            background:
              c.confidence >= 0.85
                ? "linear-gradient(135deg, #eaf8e6 0%, #dff0da 100%)"
                : c.confidence >= 0.65
                ? "linear-gradient(135deg, #fff6de 0%, #fff0bf 100%)"
                : "linear-gradient(135deg, #ffe6ec 0%, #ffd8e3 100%)",
            borderColor: "var(--border-soft)",
            color:
              c.confidence >= 0.85
                ? "#3f6b3c"
                : c.confidence >= 0.65
                ? "#7a6514"
                : "#8a4456",
          }}
        >
          {Math.round(c.confidence * 100)}%
        </div>

        <div className="text-2xl font-semibold pr-24" style={{ color: "var(--text-main)" }}>
          {mode === "reverse" ? c.answer : c.question}
        </div>

        {!show ? (
          <button onClick={() => setShow(true)} className="mt-8 app-button-primary px-5 py-2.5">
            Reveal
          </button>
        ) : (
          <>
            <div
              className="mt-6 text-base leading-7"
              style={{ color: "var(--text-soft)" }}
            >
              {mode === "reverse"
                ? c.question
                : c.answer && !c.answer.toLowerCase().includes("named concept found")
                ? c.answer
                : "No answer extracted from notes yet."}
            </div>

            {isGameMode ? (
              <div className="flex gap-3 mt-8 flex-wrap">
                <button
                  onClick={() => answerCard("correct")}
                  className="app-button-primary px-4 py-2"
                >
                  Correct
                </button>

                <button
                  onClick={() => answerCard("wrong")}
                  className="px-4 py-2 rounded-xl border"
                  style={{
                    background: "linear-gradient(135deg, #ffe6ec 0%, #ffd7e2 100%)",
                    borderColor: "var(--border-soft)",
                    color: "#8a4456",
                  }}
                >
                  Wrong
                </button>

                <button
                  onClick={() => answerCard("skip")}
                  className="app-button-secondary px-4 py-2"
                >
                  Skip
                </button>
              </div>
            ) : (
              <div className="flex gap-3 mt-8 flex-wrap">
                <button
                  onClick={() => grade("hard")}
                  className="px-4 py-2 rounded-xl border"
                  style={{
                    background: "linear-gradient(135deg, #ffe6ec 0%, #ffd7e2 100%)",
                    borderColor: "var(--border-soft)",
                    color: "#8a4456",
                  }}
                >
                  Hard
                </button>

                <button
                  onClick={() => grade("medium")}
                  className="px-4 py-2 rounded-xl border"
                  style={{
                    background: "linear-gradient(135deg, #fff6de 0%, #eef7ec 100%)",
                    borderColor: "var(--border-soft)",
                    color: "#7a6514",
                  }}
                >
                  Medium
                </button>

                <button onClick={() => grade("easy")} className="app-button-primary px-4 py-2">
                  Easy
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <div
        className="text-sm px-4 py-3 rounded-2xl border inline-block"
        style={{
          background: "rgba(255,255,255,0.72)",
          borderColor: "var(--border-soft)",
          color: "var(--text-soft)",
        }}
      >
        Card {Math.min(i + 1, cards.length)} / {cards.length}
      </div>
    </div>
  );
}