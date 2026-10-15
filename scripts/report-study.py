#!/usr/bin/env python3
"""Write a Markdown statistics report from aggregate-study.py output (all_records.csv).

Demo records are excluded. Free-text motivations and extension reasons are never
copied into the report, but participant IDs are shortened, not removed: keep the
report private like the CSVs it is built from.
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import statistics
import sys

NA = {"", "N/A"}


def utc(ms):
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def fmt(value, digits=1):
    return "–" if value is None else f"{value:.{digits}f}"


def pct(part, whole):
    return "–" if not whole else f"{100 * part / whole:.0f}%"


def mean(values):
    return statistics.mean(values) if values else None


def median(values):
    return statistics.median(values) if values else None


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def load(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or "record_type" not in rows[0]:
        raise ValueError(f"Not an aggregate-study.py all_records.csv: {path}")
    return rows


def build_report(rows, source, generated):
    metadata = [r for r in rows if r["record_type"] == "metadata"]
    real = [r for r in rows if r["record_type"] != "metadata" and r["is_demo"] == "false"]
    openings = [r for r in real if r["record_type"] == "opening"]
    sessions = [r for r in real if r["record_type"] == "session"]
    extensions = [r for r in real if r["record_type"] == "extension"]
    completed = [r for r in sessions if r["status"] == "completed"]
    timeouts = [r for r in sessions if r["status"] == "inactivity_timeout"]
    unfinished = [r for r in sessions if r["status"] not in {"completed", "inactivity_timeout"}]
    paired = [r for r in completed if r["relaxation_before"] not in NA and r["relaxation_after"] not in NA]
    participants = sorted({r["participant_id"] for r in metadata} | {r["participant_id"] for r in real})
    active = {r["participant_id"] for r in openings} | {r["participant_id"] for r in sessions}
    with_sessions = {r["participant_id"] for r in sessions}
    session_openings = {(r["participant_id"], r["opening_id"]) for r in sessions}
    started_here = [o for o in openings if (o["participant_id"], o["opening_id"]) in session_openings]
    reentries = [o for o in openings if o["session_id"] and o not in started_here]
    no_session = [o for o in openings if not o["session_id"]]
    rated_no_session = [o for o in no_session if o["relaxation_before"] not in NA]
    stamps = [int(r[k]) for r in real for k in ("opened_at_utc_ms", "started_at_utc_ms") if r.get(k)]
    span = f"{utc(min(stamps)):%Y-%m-%d %H:%M} → {utc(max(stamps)):%Y-%m-%d %H:%M} UTC" if stamps else "no activity yet"
    out = [
        "# Intentional study report", "",
        f"Generated {generated:%Y-%m-%d %H:%M} UTC from `{source}`. Activity window: {span}.",
        "Demo records are excluded. Times are UTC.", "",
        "## Overview", "",
        table(["Metric", "Value"], [
            ["Installations that uploaded", len(participants)],
            ["Installations with any tracked opening or session", len(active)],
            ["Installations that started at least one session", len(with_sessions)],
            ["Opening attempts", len(openings)],
            ["Sessions started", len(sessions)],
            ["Sessions completed with reflection", f"{len(completed)} ({pct(len(completed), len(sessions))})"],
            ["Sessions ended by inactivity timeout", f"{len(timeouts)} ({pct(len(timeouts), len(sessions))})"],
            ["Sessions still open at last upload", len(unfinished)],
            ["Extensions", len(extensions)],
        ]), "",
        "Installations are app installs, not people: a reinstall or a second phone gets a new ID.", "",
        "## Opening funnel", "",
        table(["Opening attempts", "Count", "Share"], [
            ["Started a new session", len(started_here), pct(len(started_here), len(openings))],
            ["Re-entered an already running session", len(reentries), pct(len(reentries), len(openings))],
            ["No session (gate dismissed or abandoned)", len(no_session), pct(len(no_session), len(openings))],
            ["  of which gave a baseline rating first", len(rated_no_session), pct(len(rated_no_session), len(openings))],
        ]), "",
        table(["Source", "Count"], sorted(Counter(o["opening_source"] or "unknown" for o in openings).items())), "",
        "## By app", "",
    ]
    app_rows = []
    for app in sorted({r["app"] for r in real}):
        s = [r for r in sessions if r["app"] == app]
        c = [r for r in s if r["status"] == "completed"]
        p = [r for r in paired if r["app"] == app]
        app_rows.append([
            app, sum(o["app"] == app for o in openings), len(s), len(c),
            sum(r["status"] == "inactivity_timeout" for r in s),
            f"{sum(r['task_completed'] == 'true' for r in c)}/{len(c)}",
            fmt(median([float(r["tracked_elapsed_seconds"]) / 60 for r in s if r["tracked_elapsed_seconds"]])),
            fmt(mean([float(r["relaxation_after"]) - float(r["relaxation_before"]) for r in p]), 2)])
    out += [table(["App", "Openings", "Sessions", "Completed", "Timed out", "Fulfilled", "Median used (min)",
                   "Mean relaxation change"], app_rows), ""]

    selected = [float(r["selected_minutes"]) for r in sessions if r["selected_minutes"]]
    used = [float(r["tracked_elapsed_seconds"]) / 60 for r in sessions if r["tracked_elapsed_seconds"]]
    budget = [(float(r["tracked_elapsed_seconds"]) / 60, float(r["selected_minutes"]) + float(r["extension_minutes"] or 0))
              for r in sessions if r["status"] in {"completed", "inactivity_timeout"} and r["tracked_elapsed_seconds"]]
    out += [
        "## Time", "",
        table(["Metric", "Value"], [
            ["Selected duration (min): median / mean", f"{fmt(median(selected))} / {fmt(mean(selected))}"],
            ["Foreground time used (min): median / mean", f"{fmt(median(used))} / {fmt(mean(used))}"],
            ["Total foreground time tracked (min)", fmt(sum(used))],
            ["Ended sessions within selected + extended time", f"{sum(u <= b + 0.05 for u, b in budget)}/{len(budget)}"],
        ]), "",
        table(["Selected minutes", "Sessions"], sorted(Counter(r["selected_minutes"] for r in sessions).items(),
                                                       key=lambda kv: float(kv[0] or 0))), "",
        "## Relaxation (1 = not at all, 5 = very relaxed)", "",
    ]
    before = [float(r["relaxation_before"]) for r in paired]
    after = [float(r["relaxation_after"]) for r in paired]
    changes = [a - b for a, b in zip(after, before)]
    all_before = [float(r["relaxation_before"]) for r in sessions if r["relaxation_before"] not in NA]
    out += [
        table(["Metric", "Value"], [
            ["Sessions with paired before/after ratings", len(paired)],
            ["Mean before → after (paired)", f"{fmt(mean(before), 2)} → {fmt(mean(after), 2)}"],
            ["Mean change (paired)", fmt(mean(changes), 2)],
            ["Improved / unchanged / worse", f"{sum(c > 0 for c in changes)} / {sum(c == 0 for c in changes)} / "
                                            f"{sum(c < 0 for c in changes)}"],
            ["Mean baseline, all sessions", fmt(mean(all_before), 2)],
            ["Baseline ratings left at the default 3", f"{sum(v == 3 for v in all_before)}/{len(all_before)}"],
        ]), "",
        table(["Rating", "Before (all sessions)", "After (completed)"],
              [[v, sum(float(r["relaxation_before"]) == v for r in sessions if r["relaxation_before"] not in NA),
                sum(float(r["relaxation_after"]) == v for r in completed if r["relaxation_after"] not in NA)]
               for v in range(1, 6)]), "",
        "## Intentions", "",
        table(["Metric", "Value"], [
            ["Intention fulfilled (completed sessions)",
             f"{sum(r['task_completed'] == 'true' for r in completed)}/{len(completed)}"],
            ["Sessions extended", f"{sum(int(r['extension_count'] or 0) > 0 for r in sessions)}/{len(sessions)}"],
            ["Extension minutes added", fmt(sum(float(e["extension_minutes"] or 0) for e in extensions), 0)],
        ]), "",
        table(["Purpose", "Sessions"], Counter(r["purpose"] or "unknown" for r in sessions).most_common()), "",
        "## Daily activity", "",
    ]
    days = defaultdict(lambda: [0, 0, set()])
    for o in openings:
        day = days[f"{utc(o['opened_at_utc_ms']):%Y-%m-%d}"]; day[0] += 1; day[2].add(o["participant_id"])
    for s in sessions:
        day = days[f"{utc(s['started_at_utc_ms']):%Y-%m-%d}"]; day[1] += 1; day[2].add(s["participant_id"])
    out += [table(["Date", "Openings", "Sessions", "Active installations"],
                  [[d, v[0], v[1], len(v[2])] for d, v in sorted(days.items())]), "",
            "## Per installation", ""]
    exported = {r["participant_id"]: int(r["exported_at_utc_ms"]) for r in metadata}
    part_rows = []
    for p in participants:
        s = [r for r in sessions if r["participant_id"] == p]
        part_rows.append([f"`{p[:8]}`", sum(o["participant_id"] == p for o in openings), len(s),
                          sum(r["status"] == "completed" for r in s), sum(r["status"] == "inactivity_timeout" for r in s),
                          ", ".join(sorted({r["app"] for r in real if r["participant_id"] == p})) or "–",
                          f"{utc(exported[p]):%Y-%m-%d %H:%M}" if p in exported else "–"])
    part_rows.sort(key=lambda row: (-row[2], -row[1]))
    out += [table(["Installation", "Openings", "Sessions", "Completed", "Timed out", "Apps", "Last export (UTC)"],
                  part_rows), "",
            "## Reading notes", "",
            "- Relaxation averages use only completed sessions with both ratings; timeouts record `N/A` and are excluded.",
            "- Ratings start at 3 in the UI, so a 3 may be an untouched default rather than a real answer.",
            "- Openings are observed via the accessibility service and are missed while it is disabled; an",
            "  installation with no openings acknowledged the notice but may not have enabled the service.",
            "- Small samples: treat percentages and means as descriptive, not as evidence of an effect.", ""]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="Folder written by aggregate-study.py")
    parser.add_argument("--output", type=Path, help="Report path (default: <results>/report.md); never overwritten")
    args = parser.parse_args()
    output = args.output or args.results / "report.md"
    report = build_report(load(args.results / "all_records.csv"), args.results, datetime.now(timezone.utc))
    with output.open("x", encoding="utf-8") as stream:
        stream.write(report)
    print(f"Wrote {output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, csv.Error) as error:
        print(f"Cannot write study report: {error}", file=sys.stderr)
        sys.exit(1)
