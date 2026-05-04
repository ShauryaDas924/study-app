import { authFetch } from "@/lib/auth";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const requestHeaders = new Headers(init?.headers);

  if (!requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }

  const res = await authFetch(path, {
    ...init,
    headers: requestHeaders,
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

/* =========================
   Shared Types
========================= */

export type UUID = string;

export interface HealthResponse {
  ok: true;
}

export interface NoteCreateIn {
  class_id: UUID;
  title: string;
  content_json: Record<string, unknown>;
  auto_extract?: boolean;
  mode?: string;
}

export interface NoteCreateOut {
  id: UUID;
  title: string;
  status?: string;
  progress?: number;
  mode?: string;
}

export interface NoteOut {
  id: UUID;
  title: string;
  content_json: Record<string, unknown>;
}

export interface ExtractConceptsOut {
  message: string;
  concepts: { id: UUID; name: string }[];
}


export interface StartExtractionOut {
  message: string;
  note_id: UUID;
  status: string;
  progress: number;
  mode: string;
}

export interface ExtractionStatusOut {
  note_id: UUID;
  status: "idle" | "queued" | "running" | "completed" | "failed";
  progress: number;
  mode?: string | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

/**
 * Your backend returns questions as:
 * { id, prompt } from /practice/generate and remedial routes.
 * Full question_json is server-side and used by step/hint/why-wrong routes.
 */
export interface PracticeQuestionStub {
  id: UUID;
  prompt: string;
question_json?: any;
}

export interface PracticeGenerateIn {
  class_id: UUID;
  difficulty?: number; // 1..5
  n?: number;
  subject_tag?: string;
question_type?: "open" | "mcq";
}

export interface PracticeGenerateOut {
  practice_set_id: UUID;
  questions: PracticeQuestionStub[];
}

export interface RemedialGenerateIn {
  class_id: UUID;
  n?: number;
  difficulty?: number;
  subject_tag?: string;
  lookback_days?: number;
  top_tags?: number;
  include_dependencies?: boolean;
}

export interface AttemptIn {
  user_answer_json: Record<string, unknown>;
  is_correct: boolean;
  confidence?: number; // 1..5
  time_spent_sec?: number;
  session_id?: UUID | null;
}

export interface AttemptFeedback {
  message: string;
  mistake: string;
  why: string;
}

export interface CrossConceptWeakness {
  since_days: number;
  tags: {
    tag: string;
    count: number;
    top_concepts: { concept_id: UUID; concept_name: string; count: number }[];
  }[];
  prerequisites_for_this_concept?: UUID[];
}

/**
 * NOTE: Your backend currently has a small bug in the return dict:
 * it’s missing a comma between auto_remedial_created and weakness.
 * Once you fix it, this type matches expected output.
 */
export interface SubmitAttemptOut {
  ok: true;
  feedback: AttemptFeedback | null;
  auto_remedial_created: boolean;
  weakness?: CrossConceptWeakness;
}

export interface NextStepOut {
  next_step?: string;
  message?: "Done" | string;
}

export interface CheckStepIn {
  step: string;
  step_index: number;
}

export interface CheckStepOut {
  correct: boolean;
  feedback: string;
}

export interface WhyWrongIn {
  step: string;
}

export interface WhyWrongOut {
  explanation: string;
}

export interface HintOut {
  hint: string;
}

export interface TutorAskIn {
  question: string;
}

export interface TutorAskOut {
  hint: string;
}

export interface StartExamIn {
  class_id: UUID;
  time_limit_min?: number;
  n_questions?: number;
}

export interface StartExamOut {
  exam_session_id: UUID;
  questions: PracticeQuestionStub[];
}

export interface ExamReportOut {
  accuracy: number; // percent int
  avg_time_sec?: number;
  attempts?: number;
}

export interface ReadinessOut {
  readiness_percent: number;
  weak_concepts: { concept_id: UUID; name: string; mastery_prob: number }[];
}

export interface MistakeHeatmapOutItem {
  concept_id: UUID;
  mistakes: number;
}

export interface TagFrequencyOutItem {
  tag: string;
  count: number;
}

export interface WeaknessMapOut {
  since_days: number;
  tags: {
    tag: string;
    count: number;
    top_concepts: { concept_id: UUID; concept_name: string; count: number }[];
  }[];
}

export type KnowledgeGraphNode =
  | {
      id: UUID;
      label: string;
      type: "concept";
      mastery_prob: number;
      mistake_count: number;
    }
  | {
      id: string; // "tag:..."
      label: string;
      type: "tag";
    };

export type KnowledgeGraphEdge =
  | {
      source: UUID;
      target: UUID;
      type: "prereq";
      weight: number;
    }
  | {
      source: UUID;
      target: string; // tag id
      type: "mistake_tag";
      weight: number;
    };

export interface KnowledgeGraphOut {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}

export interface PlanGenerateIn {
  class_id: UUID;
  exam_id?: UUID | null;
  exam_date_iso?: string | null;
  available_minutes_per_day?: number;
}

export interface DailyPlanTask {
  type: "review" | "practice" | "reflection";
  concept_id?: UUID;
  minutes: number;
  goal: string;
}

export interface DailyPlanDay {
  day: string; // iso date
  tasks: DailyPlanTask[];
}

export interface PlanGenerateOut {
  days_left: number;
  plan: DailyPlanDay[];
}

export interface WeeklyPlanDay {
  day: string;
  tasks: DailyPlanTask[];
}

export interface WeeklyPlanWeek {
  week: number;
  week_start: string;
  days: WeeklyPlanDay[];
}

export interface WeeklyPlanOut {
  weeks_left: number;
  days_left: number;
  weekly_plan: WeeklyPlanWeek[];
}

export interface AutoBuildDepsOut {
  edges_created: number;
  edges: { concept: string; depends_on: string }[];
}

/* =========================
   ROUTES (EXACT)
========================= */

export const api = {
  // health
  health: () => request<HealthResponse>("/health"),

  listClasses: () =>
    request<{ id: UUID; name: string; term?: string }[]>("/classes"),

  createClass: (body: { name: string; term?: string }) =>
    request<{ id: UUID; name: string; term?: string }>("/classes", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  clearClass: (classId: UUID) =>
    request<{ message: string }>(
      `/classes/${classId}/clear`,
      { method: "DELETE" }
    ),

  deleteClass: (classId: UUID) =>
    request<{ message: string }>(`/classes/${classId}`, { method: "DELETE" }),

  // notes
  createNote: (body: NoteCreateIn) =>
    request<NoteCreateOut>("/notes", { method: "POST", body: JSON.stringify(body) }),

  notesByClass: (classId: UUID) =>
    request<NoteOut[]>(`/notes/by-class/${classId}`),

  getNote: (noteId: UUID) =>
    request<NoteOut>(`/notes/${noteId}`),

  // note extraction background jobs
  startConceptExtraction: (noteId: UUID, mode?: string) =>
    request<StartExtractionOut>(`/notes/${noteId}/extract/start`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),

  getConceptExtractionStatus: (noteId: UUID) =>
    request<ExtractionStatusOut>(`/notes/${noteId}/extract/status`),
  // practice
  generatePractice: (body: PracticeGenerateIn) =>
    request<PracticeGenerateOut>("/practice/generate", { method: "POST", body: JSON.stringify(body) }),

  generateRemedial: (body: RemedialGenerateIn) =>
    request<PracticeGenerateOut>("/practice/remedial/generate", { method: "POST", body: JSON.stringify(body) }),

  submitAttempt: (questionId: UUID, body: AttemptIn) =>
    request<SubmitAttemptOut>(`/practice/questions/${questionId}/attempt`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  nextStep: (questionId: UUID, stepIndex: number) =>
    request<NextStepOut>(`/practice/questions/${questionId}/next-step?step_index=${stepIndex}`),

  checkStep: (questionId: UUID, body: CheckStepIn) =>
    request<CheckStepOut>(`/practice/questions/${questionId}/check-step`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  whyWrong: (questionId: UUID, body: WhyWrongIn) =>
    request<WhyWrongOut>(`/practice/questions/${questionId}/why-wrong`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  nextHint: (questionId: UUID, hintLevel: 1 | 2 | 3) =>
    request<HintOut>(`/practice/questions/${questionId}/next-hint?hint_level=${hintLevel}`),

  getHint: (questionId: UUID, hintLevel: 1 | 2 | 3) =>
    request<HintOut>(`/practice/questions/${questionId}/next-hint?hint_level=${hintLevel}`),

  tutorAsk: (questionId: UUID, body: TutorAskIn) =>
    request<TutorAskOut>(`/practice/questions/${questionId}/ask`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // exam
  startExam: (body: StartExamIn) =>
    request<StartExamOut>("/practice/exam/start", { method: "POST", body: JSON.stringify(body) }),

  examReport: (sessionId: UUID) =>
    request<ExamReportOut>(`/practice/exam/${sessionId}/report`),

  // readiness
  readiness: (classId: UUID) => {
    if (!classId) {
      return Promise.resolve({ readiness_percent: 0, weak_concepts: [] });
    }

    return request<ReadinessOut>(`/practice/classes/${classId}/readiness`);
  },

  // analytics
  mistakeHeatmap: (classId: UUID) =>
    request<MistakeHeatmapOutItem[]>(`/practice/analytics/mistake-heatmap/${classId}`),

  tagFrequency: () =>
    request<TagFrequencyOutItem[]>(`/practice/analytics/tag-frequency`),

  weaknessMap: (classId: UUID) =>
    request<WeaknessMapOut>(`/practice/analytics/weakness-map/${classId}`),

  knowledgeGraph: (classId: UUID) =>
    request<KnowledgeGraphOut>(`/practice/analytics/knowledge-graph/${classId}`),

  // planning
  planDaily: (body: PlanGenerateIn) =>
    request<PlanGenerateOut>(`/plan/generate`, { method: "POST", body: JSON.stringify(body) }),

  planWeekly: (body: PlanGenerateIn) =>
    request<WeeklyPlanOut>(`/plan/weekly-generate`, { method: "POST", body: JSON.stringify(body) }),

  // dependencies
  autoBuildDependencies: (classId: UUID) =>
    request<AutoBuildDepsOut>(`/practice/dependencies/auto-build/${classId}`, { method: "POST" }),
};
