import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("report_study", Path(__file__).parents[1] / "report-study.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def row(kind, id, participant="p1", **values):
    base = dict(participant_id=participant, record_type=kind, record_id=str(id), app="YouTube", is_demo="false",
                exported_at_utc_ms="1791900000000", opening_source="", opening_id="", session_id="", status="",
                opened_at_utc_ms="", started_at_utc_ms="", selected_minutes="", relaxation_before="",
                tracked_elapsed_seconds="", relaxation_after="", task_completed="", extension_count="",
                extension_minutes="", purpose="", motivation="private words")
    base.update(values)
    return base


class ReportTests(unittest.TestCase):
    def build(self):
        rows = [
            row("metadata", "study", is_demo=""), row("metadata", "study", participant="p2", is_demo=""),
            row("opening", 1, opening_source="foreground_entry", opening_id="1", session_id="s1",
                opened_at_utc_ms="1791900000000"),
            row("opening", 2, opening_source="foreground_entry", opening_id="2", session_id="s1",
                opened_at_utc_ms="1791900060000"),
            row("opening", 3, opening_source="intentional_launcher", opening_id="3", opened_at_utc_ms="1791900120000"),
            row("session", "s1", opening_id="1", session_id="s1", status="completed", started_at_utc_ms="1791900000000",
                selected_minutes="5", relaxation_before="2", relaxation_after="4", task_completed="true",
                tracked_elapsed_seconds="240", extension_count="0", extension_minutes="0", purpose="Relax"),
            row("session", "s2", opening_id="9", session_id="s2", status="inactivity_timeout",
                started_at_utc_ms="1791900200000", selected_minutes="15", relaxation_before="3", relaxation_after="N/A",
                task_completed="N/A", tracked_elapsed_seconds="60", extension_count="0", extension_minutes="0",
                purpose="Relax"),
            row("session", "demo", is_demo="true", status="completed", started_at_utc_ms="1791900000000",
                relaxation_before="1", relaxation_after="5"),
        ]
        return report.build_report(rows, "results", datetime(2026, 10, 14, tzinfo=timezone.utc))

    def test_counts_funnel_and_paired_ratings_exclude_demo_and_timeouts(self):
        text = self.build()
        self.assertIn("| Installations that uploaded | 2 |", text)
        self.assertIn("| Installations with any tracked opening or session | 1 |", text)
        self.assertIn("| Sessions started | 2 |", text)
        self.assertIn("| Started a new session | 1 | 33% |", text)
        self.assertIn("| Re-entered an already running session | 1 | 33% |", text)
        self.assertIn("| Mean before → after (paired) | 2.00 → 4.00 |", text)
        self.assertIn("| Intention fulfilled (completed sessions) | 1/1 |", text)

    def test_free_text_is_not_copied(self):
        self.assertNotIn("private words", self.build())


if __name__ == "__main__":
    unittest.main()
