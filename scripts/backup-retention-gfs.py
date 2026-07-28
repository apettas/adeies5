#!/usr/bin/env python3
"""GFS retention για offsite backups adeies5_YYYYMMDD_HHMMSS.tar

Κρατά (ένωση κανόνων):
  - όλες τις ημερήσιες των τελευταίων N ημερών
  - 1 ανά εβδομάδα για τις τελευταίες W εβδομάδες (το νεότερο κάθε ISO week)
  - 1 ανά μήνα για τους τελευταίους M μήνες (το νεότερο κάθε μήνα)
  - 1 ανά έτος για τα τελευταία Y χρόνια (το νεότερο κάθε έτους)

Διαβάζει ονόματα αρχείων από stdin (ένα ανά γραμμή).
Εκτυπώνει στη stdout τα αρχεία προς ΔΙΑΓΡΑΦΗ.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from typing import Iterable

NAME_RE = re.compile(r"^adeies5_(\d{8})_(\d{6})\.tar$")


def parse_name(name: str) -> tuple[str, date, str] | None:
    m = NAME_RE.match(name.strip())
    if not m:
        return None
    d = datetime.strptime(m.group(1), "%Y%m%d").date()
    stamp = m.group(1) + m.group(2)  # για σύγκριση νεότερου
    return name.strip(), d, stamp


def newest_per_key(items: list[tuple[str, date, str]], key_fn) -> set[str]:
    best: dict[object, tuple[str, str]] = {}
    for name, d, stamp in items:
        key = key_fn(d)
        prev = best.get(key)
        if prev is None or stamp > prev[1]:
            best[key] = (name, stamp)
    return {name for name, _ in best.values()}


def compute_keep(
    items: list[tuple[str, date, str]],
    *,
    today: date,
    keep_days: int,
    keep_weeks: int,
    keep_months: int,
    keep_years: int,
) -> set[str]:
    keep: set[str] = set()

    # Daily: όλες οι ημέρες στο [today - (keep_days-1), today]
    if keep_days > 0:
        daily_from = today - timedelta(days=keep_days - 1)
        for name, d, _ in items:
            if daily_from <= d <= today:
                keep.add(name)

    # Weekly: τελευταίες keep_weeks ISO weeks (τρέχουσα συμπεριλαμβάνεται)
    if keep_weeks > 0:
        def week_key(d: date) -> tuple[int, int]:
            return d.isocalendar()[:2]

        # Επιτρεπόμενα week keys: τρέχουσα και keep_weeks-1 προηγούμενες
        allowed_weeks: set[tuple[int, int]] = set()
        cursor = today
        while len(allowed_weeks) < keep_weeks:
            allowed_weeks.add(cursor.isocalendar()[:2])
            cursor -= timedelta(days=1)
            # προστασία από άπειρο loop σε κακά δεδομένα
            if cursor < today - timedelta(days=keep_weeks * 7 + 14):
                break

        week_items = [(n, d, s) for n, d, s in items if week_key(d) in allowed_weeks]
        keep |= newest_per_key(week_items, week_key)

    # Monthly: τελευταίοι keep_months ημερολογιακοί μήνες
    if keep_months > 0:
        allowed_months: set[tuple[int, int]] = set()
        y, m = today.year, today.month
        for _ in range(keep_months):
            allowed_months.add((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1

        def month_key(d: date) -> tuple[int, int]:
            return d.year, d.month

        month_items = [(n, d, s) for n, d, s in items if month_key(d) in allowed_months]
        keep |= newest_per_key(month_items, month_key)

    # Yearly: τελευταία keep_years ημερολογιακά έτη
    if keep_years > 0:
        allowed_years = {today.year - i for i in range(keep_years)}

        def year_key(d: date) -> int:
            return d.year

        year_items = [(n, d, s) for n, d, s in items if year_key(d) in allowed_years]
        keep |= newest_per_key(year_items, year_key)

    return keep


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GFS retention: εκτυπώνει αρχεία προς διαγραφή")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--weeks", type=int, default=4)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--years", type=int, default=10)
    p.add_argument(
        "--today",
        default=None,
        help="YYYY-MM-DD για δοκιμές (default: σήμερα)",
    )
    p.add_argument(
        "--list-keep",
        action="store_true",
        help="Εκτύπωσε KEEP αντί για DELETE",
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    today = date.fromisoformat(args.today) if args.today else date.today()
    items: list[tuple[str, date, str]] = []
    for line in sys.stdin:
        parsed = parse_name(line)
        if parsed:
            items.append(parsed)

    keep = compute_keep(
        items,
        today=today,
        keep_days=args.days,
        keep_weeks=args.weeks,
        keep_months=args.months,
        keep_years=args.years,
    )
    all_names = {n for n, _, _ in items}
    out = keep if args.list_keep else (all_names - keep)
    for name in sorted(out):
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
