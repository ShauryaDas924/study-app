import { queryClient } from "@/lib/queryClient";
import { useStore } from "@/store/useStore";


const EXACT_LOCAL_KEYS = new Set([
  "activeExtractionMeta",
  "activeExtractionNoteId",
  "flashcards",
  "practiceIndex",
]);

const LOCAL_KEY_PREFIXES = [
  "blurting_board_",
  "chat_",
  "flashcards_session_",
  "mindmap_board_",
];


export function clearClientAccountState() {
  if (typeof window !== "undefined") {
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index);
      if (
        key &&
        (EXACT_LOCAL_KEYS.has(key) || LOCAL_KEY_PREFIXES.some((prefix) => key.startsWith(prefix)))
      ) {
        localStorage.removeItem(key);
      }
    }
  }

  queryClient.clear();
  useStore.setState({
    selectedClassId: "",
    selectedNoteId: undefined,
    currentSession: undefined,
    currentQuestion: undefined,
    examTimer: 0,
    masteryProgress: 0,
    practice: { questions: [], currentIndex: 0 },
    exam: { questions: [], currentIndex: 0, time_limit_min: 60 },
  });
}
