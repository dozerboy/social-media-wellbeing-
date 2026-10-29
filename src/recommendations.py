"""Transparent, rule-based well-being suggestions from the same answers the model uses.

Separate from the machine-learning prediction: every suggestion comes from a documented rule on an
input the dataset really records (social media frequency, school-night sleep, active days, age group).
The rules use published guidelines where they exist and never claim that a change will lower the
model's estimate by any amount, or that social media causes poor mental health.

Guidelines used (checked on the CDC pages listed below):
- Sleep: 8-10 hours for teens aged 13-17; 7 or more hours for adults aged 18-60
  (CDC, citing the American Academy of Sleep Medicine): https://www.cdc.gov/sleep/about/index.html
- Activity: at least 60 minutes every day for ages 6-17:
  https://www.cdc.gov/physical-activity-basics/guidelines/children.html
- Social media: there is no numeric guideline, so the rule only reacts to the most frequent answers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

SLEEP_SOURCE = "https://www.cdc.gov/sleep/about/index.html"
ACTIVITY_SOURCE = "https://www.cdc.gov/physical-activity-basics/guidelines/children.html"
TEEN_SLEEP_MIN_HOURS = 8     # ages 13-17
ADULT_SLEEP_MIN_HOURS = 7    # ages 18-60
ACTIVITY_GUIDELINE_DAYS = 7  # 60+ minutes every day (ages 6-17)
MAX_RECOMMENDATIONS = 3

SOCIAL_MEDIA_WORDS = {1: "never", 2: "a few times a month", 3: "about once a week", 4: "a few times a week",
                      5: "about once a day", 6: "several times a day", 7: "about once an hour",
                      8: "more than once an hour"}

SUPPORT_NOTE = ("If you often feel low, stressed, anxious or not like yourself, you don't have to handle it alone. "
                "Talk to someone you trust, such as a friend, family member, teacher or school counsellor, or "
                "contact a qualified health professional. In an emergency, contact your local emergency number.")


@dataclass
class Recommendation:
    id: str
    title: str
    action: str
    reason: str
    indicators: List[str]
    priority: int                  # 1 = most relevant
    source: Optional[str] = None


@dataclass
class RecommendationResult:
    recommendations: List[Recommendation] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    not_used: List[str] = field(default_factory=list)
    more_available: int = 0
    support_note: str = SUPPORT_NOTE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _as_int(value: Any, low: int, high: int) -> Optional[int]:
    """A valid whole-number answer in [low, high], or None (missing or invalid)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or not number.is_integer() or not low <= number <= high:  # NaN check: number != number
        return None
    return int(number)


def _sleep_rule(hours: int, adult: bool, frequent_social: bool) -> Optional[Recommendation]:
    minimum = ADULT_SLEEP_MIN_HOURS if adult else TEEN_SLEEP_MIN_HOURS
    if hours >= minimum:
        return None
    guideline = ("7 or more hours for adults" if adult else "8-10 hours a night for teens aged 13-17")
    shown = "4 or less" if hours <= 4 else str(hours)
    action = ("Keep a regular sleep and wake time, including weekends, and build a short wind-down routine "
              "before bed.")
    if frequent_social:
        action += " A screen-free last half hour before sleep is one simple way to protect that routine."
    return Recommendation(
        id="sleep", title="Protect your sleep", action=action,
        reason=(f"You reported {shown} hours of sleep on school nights, below the CDC's guideline of {guideline}. "
                "In this survey, shorter sleep went together with reporting poor mental health more often "
                "(an association, not proof of cause)."),
        indicators=[f"Sleep on school nights: {shown} hours"],
        priority=1 if hours <= minimum - 2 else 2, source=SLEEP_SOURCE)


def _activity_rule(days: int) -> Optional[Recommendation]:
    if days >= ACTIVITY_GUIDELINE_DAYS:
        return None
    if days <= 2:
        title, action, priority = ("Add movement you enjoy",
                                   "Start small: pick an activity you like, such as walking, cycling, dancing or a "
                                   "sport with friends, and add it on two or three more days a week.", 1)
    else:
        title, action, priority = ("Build towards daily activity",
                                   "You're already active on several days. Try adding one more active day each "
                                   "week, working towards 60 minutes most days.", 3)
    return Recommendation(
        id="activity", title=title, action=action,
        reason=(f"You reported {days} active day{'s' if days != 1 else ''} in the past week; the CDC recommends "
                "at least 60 minutes of activity every day for ages 6-17. In this survey, more active students "
                "reported poor mental health somewhat less often (an association, not proof of cause)."),
        indicators=[f"Days active 60+ minutes: {days} of 7"], priority=priority, source=ACTIVITY_SOURCE)


def _social_media_rule(code: int) -> Optional[Recommendation]:
    if code < 6:
        return None
    words = SOCIAL_MEDIA_WORDS[code]
    return Recommendation(
        id="social_media", title="Make social media use more intentional",
        action=("Notice when and why you open apps. Turn off non-essential notifications and plan short "
                "app-free breaks, for example during homework, meals or time with friends."),
        reason=(f"You reported using social media {words}. In this survey, the most frequent users reported "
                "poor mental health more often. That is an association; it does not mean social media is "
                "harmful for you, and many frequent users feel fine."),
        indicators=[f"Social media use: {words}"], priority=1 if code == 8 else 2)


def generate_recommendations(profile: Dict[str, Any], max_items: int = MAX_RECOMMENDATIONS) -> RecommendationResult:
    """Up to `max_items` prioritised suggestions for an answer profile (same keys as the model).

    Missing or invalid answers never raise; they are listed in `not_used` and no rule uses them.
    """
    profile = profile or {}
    result = RecommendationResult()
    sleep = _as_int(profile.get("sleep_hours_approx"), 4, 10)
    days = _as_int(profile.get("active_days"), 0, 7)
    social = _as_int(profile.get("social_media_code"), 1, 8)
    adult = profile.get("age_group") == "18 or older"

    candidates: List[Recommendation] = []
    if sleep is None:
        result.not_used.append("Sleep was not answered, so no sleep suggestion is based on it.")
    else:
        rec = _sleep_rule(sleep, adult, frequent_social=social is not None and social >= 6)
        if rec:
            candidates.append(rec)
        else:
            result.strengths.append("Your school-night sleep meets the CDC guideline for your age group.")
    if days is None:
        result.not_used.append("Physical activity was not answered, so no activity suggestion is based on it.")
    else:
        rec = _activity_rule(days)
        if rec:
            candidates.append(rec)
        else:
            result.strengths.append("You meet the CDC guideline of 60 minutes of activity every day.")
    if social is None:
        result.not_used.append("Social media use was not answered, so no social media suggestion is based on it.")
    else:
        rec = _social_media_rule(social)
        if rec:
            candidates.append(rec)

    candidates.sort(key=lambda r: (r.priority, r.id))
    result.recommendations = candidates[:max_items]
    result.more_available = max(0, len(candidates) - max_items)
    if not candidates and (sleep is not None or days is not None or social is not None):
        result.strengths.append("None of the habits these rules look at stands out. Keep doing what works for you.")
    return result
