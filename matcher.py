# matcher.py
from typing import List, Dict
from database import get_user, get_all_users
from config import MAX_MATCH_RESULTS, MIN_COMMON_INTERESTS

def _parse_interests(interests_str: str) -> set:
    if not interests_str:
        return set()
    # split by comma, strip whitespace, lowercase
    parts = [p.strip().lower() for p in interests_str.split(",") if p.strip()]
    return set(parts)

def score_common_interests(set_a: set, set_b: set) -> int:
    return len(set_a & set_b)

def find_matches_for_user(user_id: str) -> List[Dict]:
    """
    Return a ranked list of candidate matches for `user_id`.
    Each candidate is a dict: {user_id, name, common_interests: [...], score: N}
    """
    me = get_user(user_id)
    if not me:
        return []

    me_interests = _parse_interests(me[2] or "")
    candidates = []
    for other in get_all_users():
        other_id, other_name, other_interests_str = other
        if other_id == user_id:
            continue
        other_interests = _parse_interests(other_interests_str or "")
        score = score_common_interests(me_interests, other_interests)
        if score >= MIN_COMMON_INTERESTS:
            candidates.append({
                "user_id": other_id,
                "name": other_name,
                "common_interests": list(me_interests & other_interests),
                "score": score
            })

    # sort by descending score (more interests in common first), then by name
    candidates.sort(key=lambda x: (-x["score"], x.get("name") or ""))
    return candidates[:MAX_MATCH_RESULTS]
