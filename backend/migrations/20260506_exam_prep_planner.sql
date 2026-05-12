-- Exam Prep Planner MVP tables.
-- Apply this manually against the same Postgres database used by DATABASE_URL.

CREATE TABLE IF NOT EXISTS exam_prep_syllabi (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id),
    filename text NOT NULL,
    mime_type text,
    raw_text text NOT NULL,
    parsed_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    parse_status text NOT NULL DEFAULT 'pending',
    parse_error text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_syllabi_user_id
    ON exam_prep_syllabi(user_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_syllabi_class_id
    ON exam_prep_syllabi(class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_syllabi_user_class
    ON exam_prep_syllabi(user_id, class_id);

CREATE TABLE IF NOT EXISTS exam_prep_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id),
    syllabus_id uuid NOT NULL REFERENCES exam_prep_syllabi(id),
    title text NOT NULL,
    exam_title text NOT NULL,
    exam_date timestamptz NOT NULL,
    available_minutes_per_day integer NOT NULL DEFAULT 60,
    intensity text NOT NULL DEFAULT 'balanced',
    starts_on timestamptz NOT NULL,
    ends_on timestamptz NOT NULL,
    plan_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_plans_user_id
    ON exam_prep_plans(user_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_plans_class_id
    ON exam_prep_plans(class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_plans_syllabus_id
    ON exam_prep_plans(syllabus_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_plans_exam_date
    ON exam_prep_plans(exam_date);

CREATE INDEX IF NOT EXISTS ix_exam_prep_plans_user_class_created
    ON exam_prep_plans(user_id, class_id, created_at DESC);

CREATE TABLE IF NOT EXISTS exam_prep_topic_predictions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id),
    syllabus_id uuid NOT NULL REFERENCES exam_prep_syllabi(id),
    exam_prep_plan_id uuid REFERENCES exam_prep_plans(id),
    topic_name text NOT NULL,
    matched_concept_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    exam_likelihood_score double precision NOT NULL DEFAULT 0,
    student_priority_score double precision NOT NULL DEFAULT 0,
    confidence text NOT NULL DEFAULT 'low',
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    missing_data jsonb NOT NULL DEFAULT '[]'::jsonb,
    recommended_study_action text NOT NULL,
    scoring_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_topic_predictions_user_id
    ON exam_prep_topic_predictions(user_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_topic_predictions_class_id
    ON exam_prep_topic_predictions(class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_topic_predictions_syllabus_id
    ON exam_prep_topic_predictions(syllabus_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_topic_predictions_plan_id
    ON exam_prep_topic_predictions(exam_prep_plan_id);

CREATE TABLE IF NOT EXISTS exam_prep_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    class_id uuid NOT NULL REFERENCES classes(id),
    exam_prep_plan_id uuid NOT NULL REFERENCES exam_prep_plans(id),
    exam_topic_prediction_id uuid REFERENCES exam_prep_topic_predictions(id),
    concept_id uuid REFERENCES concepts(id),
    planned_for timestamptz NOT NULL,
    task_type text NOT NULL,
    title text NOT NULL,
    description text,
    minutes integer NOT NULL DEFAULT 0,
    rationale text,
    status text NOT NULL DEFAULT 'pending',
    source_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_user_id
    ON exam_prep_tasks(user_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_class_id
    ON exam_prep_tasks(class_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_plan_id
    ON exam_prep_tasks(exam_prep_plan_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_prediction_id
    ON exam_prep_tasks(exam_topic_prediction_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_concept_id
    ON exam_prep_tasks(concept_id);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_planned_for
    ON exam_prep_tasks(planned_for);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_status
    ON exam_prep_tasks(status);

CREATE INDEX IF NOT EXISTS ix_exam_prep_tasks_user_class_planned
    ON exam_prep_tasks(user_id, class_id, planned_for);
