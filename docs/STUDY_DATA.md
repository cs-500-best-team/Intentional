# Collecting study data (0.7.0)

Collection runs automatically after a one-time data notice, with 512 KiB and one successful upload per 15 minutes per installation account. See [Firebase collection and researcher download](FIREBASE_SUBMISSIONS.md). Participant CSV/JSON export and sending controls are removed. Expiry/extension screens do not ask fulfillment; only the final relaxation/reflection screen records that answer.

## Participant workflow

Open Intentional and read the automatic collection notice. **Continue** acknowledges it once; **Close app** leaves with no uploads enabled. After continuing, changed data is uploaded in the background when online, subject to Android scheduling and the 15-minute minimum interval. There is no send/export button and no sharing app to select. Unchanged journals do not upload. Offline changes remain local until retry. Researchers must configure Firebase and deploy the updated rules before distributing study APKs.

The data includes free-text motivations, so the notice asks participants to avoid names or sensitive details. A random installation ID identifies updates from the same installation; it is not a name, email, Android device ID, or advertising ID. Firebase anonymous authentication adds an account UID. Researchers can keep their own participant-to-installation mapping. Reinstalling generates new identifiers.

Each acknowledged upload replaces the installation's private `latest` CSV with its full current journal. The local journal remains until deletion/uninstall. Only acknowledged snapshots are marked synced; edits arriving while a request is in flight remain pending. A journal over 512 KiB is retained locally but blocked from uploading, so researchers must monitor study duration/data volume and investigate missing updates. No manual participant fallback remains.

## One CSV, four record types

| `record_type` | Meaning |
| --- | --- |
| `metadata` | Participant ID, export time, opening-tracking start time; present even with no records. |
| `opening` | An observed app entry or a tap on Intentional’s intentional-launch button. Includes any captured draft motivation, baseline rating, chosen duration, and linked session ID. Abandoned check-ins remain in the data. |
| `session` | One started session, including incomplete sessions. Contains app, selected minutes, baseline rating, motivation, purpose, tracked elapsed seconds, after rating, fulfillment, and extension totals. |
| `extension` | A continuation reason and duration, linked to its session. |

All records include `schema_version`, `participant_id`, `exported_at_utc_ms`, `tracking_started_at_utc_ms`, `record_type`, and `record_id`. Related records use `opening_id` and `session_id`. `is_demo` identifies demos. Times ending in `_utc_ms` are Unix milliseconds in UTC; durations explicitly use minutes or seconds. Ratings are 1–5, from not at all relaxed to very relaxed. Ratings begin at the UI default of 3 unless adjusted; submitted defaults are included.

`selected_minutes` is the original selection; `extension_minutes` is additional selected time. New real sessions use `timing_method=observed_foreground`. `tracked_elapsed_seconds` accumulates intervals while the corresponding app is observed in the foreground with the screen unlocked, including extensions. Leaving, locking the screen, or entering Intentional pauses both usage and the remaining timer immediately; keyboard use in the foreground app remains counted. Returning before five minutes resumes the same interaction with its unused budget. Separate apps retain separate paused interactions.

At five minutes away, the interaction is finalized with `status=inactivity_timeout`. `relaxation_after` and `task_completed` contain the literal **N/A**, not a zero or false result; the original intention/rating and observed usage remain. The timer resets, and returning starts a new gate. This occurs without reopening Intentional or asking for a response. Paused and active interactions exported before ending still have blank outcomes. `status=completed` means an explicit reflection was submitted, while `task_completed` records the Yes/No answer.

Usage relies on delivered foreground/lock events, not a retroactive OS usage-history query. If the process dies, recovery pauses at its last checkpoint (at most five seconds of uncheckpointed usage may be lost while the service is running normally); unobserved downtime is not fabricated as usage. Paused deadlines survive restart; reboot recovery uses wall time, so changing the phone clock can affect that case. If Android suspends execution, finalization occurs on the next tick/reopen and records the original five-minute deadline. Picture-in-picture and background audio are not counted as foreground usage when another app is foregrounded. Device event behavior needs testing.

Older records keep their original timing method: `elapsed_until_checkin` for 0.4.0, or `legacy_capped_elapsed` for older versions. Do not reinterpret those durations as foreground time. Demo sessions use `demo_elapsed` and continue ticking in Intentional without real app detection.

## Counting openings accurately

Count `opening` rows, not `session` rows. `opening_source=foreground_entry` means the enabled accessibility service observed a transition into the supported native app; `intentional_launcher` means the user requested a session through Intentional, possibly stepping away before launching. Both count as **opening attempts**, and the summary separates them. Repeated window events within the same foreground app do not count again. Returns initiated by Intentional to start/resume/extend are suppressed for up to five seconds so the same guided entry is not counted twice. Banner/dialog events from Intentional are ignored as app transitions.

Counts are observations, not a complete phone usage log. Tracking starts with this version, cannot reconstruct older openings, and misses entries while the service is disabled or stopped. The first observed app after a service restart may be counted as a new entry. Browser use, YouTube Music, and third-party clients are outside scope. `tracking_started_at_utc_ms` marks the start of retained tracking, not proof that the service remained enabled. Deleting the journal clears openings too and resets that timestamp. Previously exported data cannot be recalled.

No 500-session truncation is applied from this version onward. Already-discarded records from older versions cannot be recovered. The screen still shows only the latest 30 sessions, but the CSV contains all retained data.

## Researcher workflow

Download the private Firebase CSVs with a researcher account, then aggregate:

```sh
python3 scripts/download-study.py --project YOUR_PROJECT_ID --output study-exports
python3 scripts/aggregate-study.py study-exports --output study-results
```

Python 3.9+ is sufficient; no packages are required. Use a new output folder each run. The script searches the input folder recursively and produces:

- `all_records.csv`: all unique records across participants, including demo and incomplete rows, with the latest export of each record retained.
- `participant_app_summary.csv`: one row per participant/app with opening attempts by source, sessions started/completed, fulfilled intentions, mean selected duration, and paired before/after relaxation means and changes. `sessions_ended_without_response` counts inactivity timeouts. `total_ended_tracked_seconds` and `mean_ended_tracked_seconds` include both explicit completions and timeouts, so unattended usage is retained. Existing `*_completed_tracked_seconds` columns include only explicit reflections. Demo sessions are excluded. Incomplete sessions and N/A outcomes never enter outcome averages; empty averages stay blank.

Repeated submissions are deduplicated by participant ID + record type + record ID, using the latest export timestamp. Do not change the phone’s date/time during the study; export ordering uses its wall clock. A later export does not remove records previously received if the participant has since deleted their local journal. Researcher deletion requests must therefore be handled separately. Raw motivation strings are preserved apart from CSV escaping and a leading apostrophe for strings that could be interpreted as spreadsheet formulas. CSV parsers correctly handle quoted commas, newlines, and Unicode.

## Statistics report (rerun any time)

To refresh the numbers as more people use the app, sign in once with `gcloud auth login`, then run from the project root:

```sh
scripts/study-report.sh              # defaults to project intentional-1c8bd
scripts/study-report.sh OTHER_PROJECT_ID
```

It runs the download, aggregation, and `scripts/report-study.py` in sequence and **replaces** `study-exports/` and `study-results/` each time, so those folders always hold the latest data. The new data is built in temporary folders and swapped in only after the download and aggregation succeed; a failed run keeps the previous folders. Copy a folder elsewhere first if you want to keep a snapshot. Open `study-results/report.md` for the overview, opening funnel, per-app figures, time used vs selected, paired relaxation change and rating distribution, fulfilment, daily activity, and a per-installation table. Demo records are excluded; free-text motivations and extension reasons are not copied into the report. To rebuild only the report, delete `study-results/report.md` and run `python3 scripts/report-study.py study-results` (it refuses to overwrite an existing report).

The report shortens installation IDs but is still participant data: both folder patterns are gitignored, so keep reports out of git and share them only privately.

To remove a test or demo installation from the database, delete both `intentionalStudyParticipants/{uid}` and `intentionalStudyParticipants/{uid}/intentionalStudyExports/latest` (Firestore does not cascade deletes), then uninstall or clear data on that phone, or it will upload again.

## Verify on study phones

Try direct and Intentional-initiated openings, declining the opening prompt, finishing early, and extending. Confirm one guided launch is not double-counted. Check notice acknowledgment, automatic updates to `latest`, no unchanged uploads, the cooldown across restart, offline retry, and reboot persistence. Download twice into separate folders and aggregate: counts should not double. A running/paused session should have blank after-rating until answered or timed out. Confirm old journals still load and reinstalling changes the participant ID. Background scheduling, Firebase rules, and accessibility behavior need on-device/emulator verification.
