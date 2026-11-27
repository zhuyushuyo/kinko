"""How safe one account is, from what KINKO knows about it. No Qt.

Three levels, judged only on what the owner can act on:

  high  Nothing left to do: a strong password used by no other account, changed within a year, and
        two-step verification switched on - or not offered by the service at all.
  mid   Could be better: a fair or older password, or two-step verification the service offers but
        that is not switched on. For finance accounts, also when nobody has checked whether it is
        offered yet (nearly every bank and broker offers it).
  low   Fix soon: a weak password, or one that another account also uses.

A service that has no two-step verification is never marked down for it. Only active accounts with
a password get a level; closed accounts and records without a password (a pension number, say) do not.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LEVELS = ("high", "mid", "low")
LOW_REASONS = ("reused", "weak")
MID_REASONS = ("fair", "old", "twofa_off", "twofa_check")
REASONS = LOW_REASONS + MID_REASONS
WEAK_MAX = 1  # strength scores 0-1 are weak
FAIR_SCORE = 2  # 2 is fair; 3-4 strong
TWOFA_EXPECTED = ("finance",)  # categories where an unchecked 2FA counts as "check it"


@dataclass
class Safety:
    level: str  # high / mid / low
    reasons: list[str] = field(default_factory=list)  # from REASONS, the most serious first
    twofa: str = "unknown"  # on / off / none / unknown, or "na" when the account's type has no 2FA field
    score: int = 0  # password strength 0-4
    reused: int = 0  # how many other active accounts use the same password


def assess(*, score: int, reused: int = 0, old: bool = False, twofa: str = "unknown",
           category: str = "", has_twofa: bool = True) -> Safety:
    """has_twofa: whether the account's type has a 2FA field (if not, 2FA does not count)."""
    if not has_twofa and twofa == "unknown":
        twofa = "na"
    reasons: list[str] = []
    if reused:
        reasons.append("reused")
    if score <= WEAK_MAX:
        reasons.append("weak")
    elif score == FAIR_SCORE:
        reasons.append("fair")
    if old:
        reasons.append("old")
    if twofa == "off":
        reasons.append("twofa_off")
    elif twofa == "unknown" and category in TWOFA_EXPECTED:
        reasons.append("twofa_check")
    if any(r in LOW_REASONS for r in reasons):
        level = "low"
    elif reasons:
        level = "mid"
    else:
        level = "high"
    return Safety(level, reasons, twofa, score, reused)
