-- Preserve plan recommendations when materials are re-extracted.
-- Existing extracted questions remain active; newer extraction runs can mark older
-- rows stale without deleting recommendation-linked history.

ALTER TABLE exam_prep_extracted_questions
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';

ALTER TABLE exam_prep_extracted_questions
    ALTER COLUMN status SET DEFAULT 'active';

UPDATE exam_prep_extracted_questions
SET status = 'active'
WHERE status IS NULL;

ALTER TABLE exam_prep_extracted_questions
    ALTER COLUMN status SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_exam_prep_extracted_questions_status
    ON exam_prep_extracted_questions(status);

CREATE INDEX IF NOT EXISTS ix_exam_prep_extracted_questions_material_status
    ON exam_prep_extracted_questions(material_id, status);
