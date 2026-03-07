import { create } from "zustand";
import type { PracticeQuestionStub, UUID } from "@/lib/api";

export interface PracticeSessionState {
  practice_set_id?: UUID;
  questions: PracticeQuestionStub[];
  currentIndex: number;
}

export interface ExamSessionState {
  exam_session_id?: UUID;
  questions: PracticeQuestionStub[];
  currentIndex: number;
  time_limit_min: number;
  started_at_ms?: number;
}

interface AppState {
  selectedClassId: UUID;
selectedNoteId?: UUID;
  currentSession?: UUID;
  currentQuestion?: PracticeQuestionStub;

  examTimer: number;
  masteryProgress: number;

  practice: PracticeSessionState;
  exam: ExamSessionState;

  setSelectedClassId: (id: UUID) => void;
  setSelectedNoteId: (id?: UUID) => void;
  setPracticeSession: (
    practice_set_id: UUID,
    questions: PracticeQuestionStub[]
  ) => void;

  setPracticeIndex: (idx: number) => void;

  setExamSession: (
    exam_session_id: UUID,
    questions: PracticeQuestionStub[],
    time_limit_min: number
  ) => void;

  setExamIndex: (idx: number) => void;

  setExamTimer: (seconds: number) => void;
  resetExamTimer: () => void;

  setMasteryProgress: (pct: number) => void;
}

export const useStore = create<AppState>((set, get) => ({
  selectedClassId: "" as UUID,
selectedNoteId: undefined,
  examTimer: 0,
  masteryProgress: 0,

  practice: {
    questions: [],
    currentIndex: 0,
  },

  exam: {
    questions: [],
    currentIndex: 0,
    time_limit_min: 60,
  },

  // -----------------
  // CLASS
  // -----------------
  setSelectedClassId: (id) =>
  set({ 
    selectedClassId: id,
    selectedNoteId: undefined
  }),
setSelectedNoteId: (id) =>
  set({ selectedNoteId: id }),
  // -----------------
  // PRACTICE
  // -----------------
  setPracticeSession: (practice_set_id, questions) =>
    set({
      practice: {
        practice_set_id,
        questions,
        currentIndex: 0,
      },
      currentQuestion: questions[0],
    }),

  setPracticeIndex: (idx) => {
    const { practice } = get();

    const safe = Math.max(
      0,
      Math.min(idx, practice.questions.length - 1)
    );

    // ✅ SAVE progress
    localStorage.setItem(
      "practiceIndex",
      safe.toString()
    );

    set({
      practice: {
        ...practice,
        currentIndex: safe,
      },
      currentQuestion: practice.questions[safe],
    });
  },

  // -----------------
  // EXAM
  // -----------------
  setExamSession: (
    exam_session_id,
    questions,
    time_limit_min
  ) =>
    set({
      currentSession: exam_session_id,
      exam: {
        exam_session_id,
        questions,
        currentIndex: 0,
        time_limit_min,
        started_at_ms: Date.now(),
      },
      currentQuestion: questions[0],
      examTimer: 0,
    }),

  setExamIndex: (idx) => {
    const { exam } = get();

    const safe = Math.max(
      0,
      Math.min(idx, exam.questions.length - 1)
    );

    set({
      exam: {
        ...exam,
        currentIndex: safe,
      },
      currentQuestion: exam.questions[safe],
    });
  },

  setExamTimer: (seconds) =>
    set({ examTimer: seconds }),

  resetExamTimer: () =>
    set({ examTimer: 0 }),

  // -----------------
  // MASTERY
  // -----------------
  setMasteryProgress: (pct) =>
    set({
      masteryProgress: Math.max(
        0,
        Math.min(100, pct)
      ),
    }),
}));