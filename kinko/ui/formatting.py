"""Dates and durations in the current language."""
from __future__ import annotations

from datetime import datetime

from ..core.model import parse_iso
from ..i18n import language, tr


def fmt_date(iso: str | None, with_time: bool = False) -> str:
    dt = parse_iso(iso)
    if dt is None:
        return tr("common.unknown")
    if language() == "en":
        return dt.strftime("%b %d, %Y %H:%M" if with_time else "%b %d, %Y")
    s = f"{dt.year}年{dt.month}月{dt.day}日"
    return s + dt.strftime(" %H:%M") if with_time else s


def fmt_relative_day(iso: str | None) -> str:
    dt = parse_iso(iso)
    if dt is None:
        return tr("common.never")
    now = datetime.now().astimezone()
    if dt.date() == now.date():
        return tr("time.today", t=dt.strftime("%H:%M"))
    return fmt_date(iso)


def months_between(iso: str | None) -> int | None:
    dt = parse_iso(iso)
    if dt is None:
        return None
    now = datetime.now().astimezone()
    return (now.year - dt.year) * 12 + now.month - dt.month - (1 if now.day < dt.day else 0)


def fmt_age(iso: str | None) -> str:
    m = months_between(iso)
    if m is None:
        return ""
    if m < 1:
        return tr("age.recent")
    y, mo = divmod(m, 12)
    if y and mo:
        return tr("age.ym", y=y, m=mo)
    if y:
        return tr("age.y", y=y)
    return tr("age.m", m=mo)
