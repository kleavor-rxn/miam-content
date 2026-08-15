"""Extension déterministe du calendrier 'Recette du jour'."""
import hashlib
from datetime import date, timedelta

NO_REPEAT_DAYS = 14
HORIZON_DAYS = 30
KEEP_PAST_DAYS = 60   # l'app n'affiche que 30 jours d'historique (spec §5.4)


def _pick(country: str, day: str, candidates: list[str]) -> str:
    digest = hashlib.sha256(f"{country}:{day}".encode()).hexdigest()
    return candidates[int(digest, 16) % len(candidates)]


def extend_daily_picks(existing: list[dict], recipe_ids: list[str],
                       country: str, today: date) -> list[dict]:
    ids = sorted(recipe_ids)
    if not ids:
        return []
    cutoff = today - timedelta(days=KEEP_PAST_DAYS)
    valid = {p["date"]: p["recipeID"] for p in existing
             if p["recipeID"] in ids and date.fromisoformat(p["date"]) >= cutoff}
    horizon = today + timedelta(days=HORIZON_DAYS)
    start = min([date.fromisoformat(d) for d in valid] + [today])
    picks: list[dict] = []
    day = start
    while day <= horizon:  # les picks préservés au-delà de l'horizon sont tronqués (churn théorique accepté)
        key = day.isoformat()
        if key in valid:
            rid = valid[key]
        elif day >= today:
            # ni les 13 picks précédents, ni les picks déjà attribués dans les 13 jours suivants
            recent = {p["recipeID"] for p in picks[-(NO_REPEAT_DAYS - 1):]}
            ahead = {valid[k] for k in
                     ((day + timedelta(days=n)).isoformat()
                      for n in range(1, NO_REPEAT_DAYS)) if k in valid}
            candidates = [i for i in ids if i not in recent | ahead] or ids
            rid = _pick(country, key, candidates)
        else:
            day += timedelta(days=1)
            continue  # trou dans le passé : on ne réécrit pas l'histoire
        picks.append({"date": key, "recipeID": rid})
        day += timedelta(days=1)
    return picks
