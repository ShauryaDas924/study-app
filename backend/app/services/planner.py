from datetime import datetime, timezone, timedelta

def build_study_plan(
    exam_date: datetime,
    mastery_rows: list[dict],
    available_minutes_per_day: int = 60
):

    now = datetime.now(timezone.utc)
    days_left = max(1, (exam_date - now).days)

    # Sort by priority:
    # 1) Due reviews first
    # 2) Weak mastery

    def priority_key(r):

        due_score = 0

        if r.get("next_review_at") and r["next_review_at"] <= now:
            due_score = -1

        mastery = r.get("mastery_prob", 0.35)

        return (due_score, mastery)

    mastery_rows = sorted(mastery_rows, key=priority_key)
    
    n = len(mastery_rows)   # ADD THIS

    plan = []

    for d in range(days_left):

        day_date = (now + timedelta(days=d)).date().isoformat()

        remaining = available_minutes_per_day

        tasks = []

        # rotate starting point
        start_index = d % n if n > 0 else 0
    
        ordered = mastery_rows[start_index:] + mastery_rows[:start_index]

        # =====================
        # ADAPTIVE CONCEPT BLOCKS
        # =====================

        def concept_priority(r):

            mastery = r.get("mastery_prob", 0.35)
        
            # Weak concepts
            weakness_score = 1 - mastery

            # Due reviews
            due_score = 0
            if r.get("next_review_at") and r["next_review_at"] <= now:
                due_score = 0.5

            # Mistakes
            mistake_score = r.get("mistake_count", 0) * 0.15
    
            # Exam importance
            exam_score = r.get("exam_importance", 0.5)

            return (
                weakness_score
                + due_score
            + mistake_score
                + exam_score
            )


        weighted = sorted(
            ordered,
            key=concept_priority,
            reverse=True
        )

        i = 0

        while remaining > 25 and weighted:

            r = weighted[i % len(weighted)]

            mastery = r.get("mastery_prob", 0.35)
    
            if mastery < 0.3:
                minutes = 20
            elif mastery < 0.5:
                minutes = 15
            elif mastery < 0.7:
                minutes = 10
            else:
                minutes = 5

            if remaining < minutes:
                break

            tasks.append({
                "type": "concept",
                "concept_id": str(r["concept_id"]),
                "concept_name": r.get("name","concept"),
                "mastery": mastery,
                "minutes": minutes,
                "goal": f"""
        Study {r.get("name","concept")}:
        • Definition: {r.get("definition","")}
        • When to use: {r.get("when_to_use","")}
        • Common pitfall: {r.get("pitfalls","")}
        """
            })

            remaining -= minutes

            i += 1

        # =====================
        # PRACTICE BLOCK
        # =====================

        practice_minutes = max(20, remaining - 8)

        tasks.append({
            "type":"practice",
            "minutes": practice_minutes,
            "goal":
            "Solve exam-style problems; justify method selection."
        })

        remaining -= practice_minutes

        # =====================
        # REFLECTION
        # =====================

        reflection_minutes = max(5, remaining)

        tasks.append({
            "type":"reflection",
            "minutes": reflection_minutes,
            "goal":
            "Log 1 mistake pattern + detection rule."
        })

        plan.append({
            "day": day_date,
            "tasks": tasks
        })

    return {
        "days_left": days_left,
        "plan": plan
    }
    

def build_weekly_curriculum(
    exam_date: datetime,
    mastery_rows: list[dict],
    available_minutes_per_day: int = 60
):
    """
    Returns a week-by-week study plan until exam_date.
    mastery_rows items: {"concept_id": UUID/str, "name": str, "mastery_prob": float, "next_review_at": datetime|None}
    """
    now = datetime.now(timezone.utc)
    days_left = max(1, (exam_date - now).days)
    weeks = (days_left + 6) // 7

    # sort weakest first
    mastery_rows = sorted(mastery_rows, key=lambda r: r["mastery_prob"])

    out = []
    for w in range(weeks):
        week_start = (now + timedelta(days=w*7)).date()
        week_days = []

        for d in range(7):
            day_dt = now + timedelta(days=w*7 + d)
            if day_dt > exam_date:
                break

            # due reviews = next_review_at <= today
            due = [
                r for r in mastery_rows
                if r.get("next_review_at") is not None and r["next_review_at"] <= day_dt
            ]

            # fallback: weakest concepts
            weak = mastery_rows[: min(4, len(mastery_rows))]

            # choose targets (prefer due, then weak)
            targets = []
            seen = set()
            for r in due + weak:
                cid = str(r["concept_id"])
                if cid not in seen:
                    targets.append(r)
                    seen.add(cid)
                if len(targets) >= 3:
                    break

            tasks = []

            # review blocks
            for t in targets[:2]:
                tasks.append({
                    "type": "review",
                    "concept_id": str(t["concept_id"]),
                    "minutes": max(10, available_minutes_per_day // 6),
                    "goal": "Rewrite definition + when-to-use + 1 pitfall, then do 1 mini example."
                })

            # practice block
            tasks.append({
                "type": "practice",
                "minutes": max(25, available_minutes_per_day // 2),
                "goal": "Solve exam-style questions; justify method selection."
            })

            # reflection / error log
            tasks.append({
                "type": "reflection",
                "minutes": 8,
                "goal": "Log 1 mistake pattern + a detection rule."
            })

            week_days.append({
                "day": day_dt.date().isoformat(),
                "tasks": tasks
            })

        out.append({
            "week": w + 1,
            "week_start": week_start.isoformat(),
            "days": week_days
        })

    return {
        "weeks_left": weeks,
        "days_left": days_left,
        "weekly_plan": out
    }
