from datetime import datetime, timezone
import math

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def apply_forgetting(mastery: float, days: float, lam: float = 0.05) -> float:
    # mastery *= exp(-λ * days)
    return mastery * math.exp(-lam * max(0.0, days))

def update_mastery_value(mastery, correct, difficulty, confidence, time_spent):
    # Bayesian-style update
    p = mastery

    # likelihoods
    if correct:
        likelihood = 0.7 + 0.05*difficulty
    else:
        likelihood = 0.3 - 0.05*difficulty

    likelihood *= (0.8 + 0.05*confidence)

    # Bayes update
    numerator = likelihood * p
    denominator = numerator + (1-likelihood)*(1-p)

    if denominator == 0:
        return p

    posterior = numerator / denominator

    return max(0.01, min(0.99, posterior))

def days_since(dt: datetime | None) -> float:
    if dt is None:
        return 0.0
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 86400.0
    
def suggest_difficulty(mastery_prob: float) -> int:
    if mastery_prob < 0.4:
        return 2
    elif mastery_prob < 0.7:
        return 3
    else:
        return 4
        
def next_review_days(mastery_prob: float, recent_mistakes: int = 0):

    if recent_mistakes >= 3:
        return 1

    if mastery_prob < 0.4:
        return 1
    elif mastery_prob < 0.7:
        return 4
    elif mastery_prob < 0.85:
        return 7
    else:
        return 14
