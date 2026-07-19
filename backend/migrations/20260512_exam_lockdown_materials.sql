-- Exam Lockdown / evidence-based exam prep MVP tables.
-- Apply this manually against the same Postgres database used by DATABASE_URL.

ALTER TABLE exam_prep_plans
    ALTER COLUMN syllabus_id DROP NOT NULL;

ALTER TABLE exam_prep_topic_predictions
    ALTER COLUMN syllabus_id DROP NOT NULL;

ALTER TABLE exam_prep_plans
    ADD COLUMN IF NOT EXISTS target_score numeric,
    ADD COLUMN IF NOT EXISTS target_grade text,
    ADD COLUMN IF NOT EXISTS current_scores_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS weak_topics_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS selected_material_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;

CREATE TABLE IF NOT EXISTS exam_prep_materials (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    filename text NOT NULL,
    mime_type text,
    material_type text NOT NULL,
    raw_text text,
    extraction_status text NOT NULL DEFAULT 'pending',
    parse_error text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_materials_user_class
    ON exam_prep_materials(user_id, class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_materials_class_type
    ON exam_prep_materials(class_id, material_type);

CREATE INDEX IF NOT EXISTS ix_exam_prep_materials_created_at
    ON exam_prep_materials(created_at);

CREATE TABLE IF NOT EXISTS exam_prep_extracted_questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    material_id uuid NOT NULL REFERENCES exam_prep_materials(id) ON DELETE CASCADE,
    problem_number text,
    prompt_text text NOT NULL,
    answer_text text,
    solution_text text,
    topic_name text,
    concept_id uuid,
    source_ref_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence numeric,
    extraction_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_extracted_questions_user_class
    ON exam_prep_extracted_questions(user_id, class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_extracted_questions_material_id
    ON exam_prep_extracted_questions(material_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_extracted_questions_topic_name
    ON exam_prep_extracted_questions(topic_name);

CREATE INDEX IF NOT EXISTS ix_exam_prep_extracted_questions_concept_id
    ON exam_prep_extracted_questions(concept_id);

CREATE TABLE IF NOT EXISTS exam_prep_recommended_questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    plan_id uuid NOT NULL REFERENCES exam_prep_plans(id) ON DELETE CASCADE,
    extracted_question_id uuid NOT NULL REFERENCES exam_prep_extracted_questions(id) ON DELETE CASCADE,
    topic_prediction_id uuid,
    rank integer NOT NULL DEFAULT 0,
    why_selected text,
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence numeric,
    status text NOT NULL DEFAULT 'recommended',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_recommended_questions_user_class
    ON exam_prep_recommended_questions(user_id, class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_recommended_questions_plan_id
    ON exam_prep_recommended_questions(plan_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_recommended_questions_extracted_question_id
    ON exam_prep_recommended_questions(extracted_question_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_recommended_questions_status
    ON exam_prep_recommended_questions(status);

CREATE TABLE IF NOT EXISTS exam_lockdown_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    plan_id uuid NOT NULL REFERENCES exam_prep_plans(id) ON DELETE CASCADE,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    status text NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_sessions_user_class
    ON exam_lockdown_sessions(user_id, class_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_sessions_plan_id
    ON exam_lockdown_sessions(plan_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_sessions_status
    ON exam_lockdown_sessions(status);

CREATE TABLE IF NOT EXISTS exam_lockdown_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    session_id uuid REFERENCES exam_lockdown_sessions(id) ON DELETE SET NULL,
    plan_id uuid NOT NULL REFERENCES exam_prep_plans(id) ON DELETE CASCADE,
    recommended_question_id uuid NOT NULL REFERENCES exam_prep_recommended_questions(id) ON DELETE CASCADE,
    user_answer_text text,
    confidence integer,
    time_spent_sec integer,
    tutor_feedback_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'attempted',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_attempts_user_class
    ON exam_lockdown_attempts(user_id, class_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_attempts_plan_id
    ON exam_lockdown_attempts(plan_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_attempts_recommended_question_id
    ON exam_lockdown_attempts(recommended_question_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_attempts_status
    ON exam_lockdown_attempts(status);

CREATE TABLE IF NOT EXISTS exam_lockdown_pitfalls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    attempt_id uuid REFERENCES exam_lockdown_attempts(id) ON DELETE CASCADE,
    plan_id uuid NOT NULL REFERENCES exam_prep_plans(id) ON DELETE CASCADE,
    topic_name text,
    category text NOT NULL,
    tag text,
    explanation text,
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_pitfalls_user_class
    ON exam_lockdown_pitfalls(user_id, class_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_pitfalls_plan_id
    ON exam_lockdown_pitfalls(plan_id);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_pitfalls_topic_name
    ON exam_lockdown_pitfalls(topic_name);

CREATE INDEX IF NOT EXISTS ix_exam_lockdown_pitfalls_category
    ON exam_lockdown_pitfalls(category);

CREATE UNIQUE INDEX IF NOT EXISTS ux_student_pitfalls_user_class_pitfall
    ON student_pitfalls(user_id, class_id, pitfall);
