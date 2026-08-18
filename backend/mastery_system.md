# Mastery implementation note

This document describes the current code, not a validated learning-science model. The primary implementation is in `app/services/mastery.py` and `app/routers/practice.py`; flashcard and homework flows also modify mastery.

## Stored state

Each `(user_id, concept_id)` mastery row contains:

- `mastery_prob`, initialized to `0.35`;
- `last_practiced_at` and `last_updated_at`;
- `next_review_at`.

Attempt-driven changes also append a `MasteryHistory` row. Values are estimates clamped away from absolute certainty, not grades or calibrated probabilities.

## Attempt correctness

Attempt input includes answer JSON, a submitted correctness flag, confidence `1..5`, time spent `0..86400` seconds, and an optional exam session.

- For `mcq`, the backend ignores the submitted correctness flag and compares a bounded integer `selected_index` with the stored `correct_index` and options.
- For every non-MCQ type, correctness is self-assessed by the student/client.

The question and optional exam session are first scoped to the authenticated user (and matching course for the session).

## Forgetting at update time

Before a practice-attempt update, the stored value `p` is decayed according to days since the last practice:

```text
p_decayed = p × exp(-0.05 × max(days_since_last_practice, 0))
```

If the concept has never been practiced, elapsed days are treated as zero. Decay is applied only when an attempt is submitted; it is not a scheduled background process and is not applied when readiness is read.

## Bayesian-style attempt update

The code derives a likelihood from correctness, question difficulty `d`, and confidence `c`:

```text
if correct:
    likelihood = 0.7 + 0.05 × d
else:
    likelihood = 0.3 - 0.05 × d

likelihood = likelihood × (0.8 + 0.05 × c)
```

It then computes:

```text
posterior = likelihood × p_decayed
            / (likelihood × p_decayed + (1 - likelihood) × (1 - p_decayed))

mastery_prob = clamp(posterior, 0.01, 0.99)
```

If the denominator is zero, the decayed value is returned. `time_spent_sec` is stored and passed into the function but does not affect this formula.

## Review scheduling

After a practice update, the next review is chosen from the updated mastery and the total stored mistake-log count for the concept:

| Condition | Next review |
| --- | --- |
| at least 5 mistake logs | 1 day |
| mastery below `0.6` | 2 days |
| mastery below `0.8` | 4 days |
| otherwise | 7 days |

The standalone `next_review_days` helper contains a different `1/4/7/14` heuristic and is not the scheduler used by attempt submission.

## Other update paths

- A detected homework misconception applies the same Bayesian-style function as an incorrect difficulty-3/confidence-2 result to the retrieved concepts. That path does not first apply forgetting or update the normal practice timestamps/history.
- When a mastery row already exists, flashcard review applies direct deltas: easy is `min(0.95, p + 0.05)`, medium is `min(0.95, p + 0.02)`, and hard is `max(0.05, p - 0.07)`. These are branch-specific one-sided clamps, not a shared `0.05..0.95` clamp. The review also updates flashcard spacing state.

Mastery is therefore a shared heuristic signal with more than one update policy, not a single formally consistent estimator.

## Readiness and selection

Class readiness is the arithmetic mean of stored mastery for all class concepts; concepts without a row contribute `0.35`. It returns the six weakest concepts by that stored value. It does not filter to exam-relevant concepts or dynamically decay values at read time.

Practice generation sorts by mastery and samples mainly from a weaker pool, with some wider coverage for exam-tagged sets. Repeated failures can trigger a three-question remedial set.

## Known limitations

- The formula has not been empirically calibrated or benchmarked.
- Open-response correctness is self-reported.
- Timing does not influence mastery.
- Confidence is a multiplier, not a separately calibrated signal.
- Mistake counts used by scheduling are all-time counts, despite some variable names suggesting recency.
- Flashcard, homework, and practice paths are not mathematically unified.
- Readiness is a simple stored average and can look stale until another attempt updates a concept.

Any behavior change should update deterministic tests and this note together.
