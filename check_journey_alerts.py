"""Focused checks for saved-journey in-app alerts."""

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

import hamar_workspace
from project_alerts import build_alerts, load_snapshot
from workspace_service import Workspace


def saved_journey():
    return {
        "version": 1,
        "id": "saved-ringgata",
        "name": "Ringgata to Ankerskogen",
        "case_id": "hamar-urban",
        "origin": {"coordinates": [60.7988246, 11.0881825], "label": "Ringgata crossing"},
        "destination": {"coordinates": [60.8031248, 11.0702252], "label": "Ankerskogen park path"},
    }


def unrelated_saved_journey(workspace):
    journey = next(
        item for item in workspace.get_case("hamar-urban")["journeys"]
        if item["id"] == "junction-to-north-path"
    )
    return {
        "version": 1,
        "id": "saved-furubergvegen",
        "name": "Junction to north path",
        "case_id": "hamar-urban",
        "origin": {
            "coordinates": journey["origin"]["coordinates"],
            "label": journey["origin"]["label"],
        },
        "destination": {
            "coordinates": journey["destination"]["coordinates"],
            "label": journey["destination"]["label"],
        },
    }


def koigen_monitor_request():
    return {
        "case_id": "koigen-demo",
        "assessment_date": "2026-11-18",
        "modeled_section_confirmation": True,
        "projects": [{
            "name": "Koigen candidate",
            "start_date": "2026-11-18",
            "end_date": "2026-11-18",
            "sections": ["koigen-candidate-closure"],
            "hypothetical": True,
        }],
    }


class JourneyAlertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = Workspace(ROOT)
        cls.base = load_snapshot(ROOT, "base")
        cls.current = load_snapshot(ROOT, "current")

    def check(self, previous=None, revision="current"):
        return build_alerts(
            self.workspace,
            ROOT,
            [saved_journey()],
            previous or [],
            revision,
            "2026-11-18",
        )

    def test_current_projects_create_approaching_and_active_route_alerts(self):
        result = self.check()
        kinds = [alert["kind"] for alert in result["alerts"]]
        self.assertIn("approaching_works", kinds)
        self.assertIn("active_impact", kinds)
        for alert in result["alerts"]:
            self.assertTrue(alert["synthetic"])
            self.assertEqual(alert["journey_id"], "saved-ringgata")
            self.assertTrue(alert["checked_at"])
            self.assertTrue(alert["source"]["snapshot_sha256"])
            self.assertTrue(alert["source"]["snapshot_file"])
        impact = next(alert for alert in result["alerts"] if alert["kind"] == "active_impact")
        self.assertEqual(
            (
                impact["route_effect"]["baseline_metres"],
                impact["route_effect"]["metres"],
            ),
            (1384, 2086),
        )

    def test_date_extension_compares_previous_snapshot_and_is_stable(self):
        previous = [
            {
                key: project.get(key)
                for key in (
                    "id", "start_date", "end_date", "section_ids",
                    "reopening_confirmed", "reopening_confirmed_at",
                )
            }
            for project in self.base["projects"]
        ]
        first = self.check(previous)
        second = self.check(previous)
        changed = [
            alert for alert in first["alerts"]
            if alert["kind"] == "dates_changed"
            and alert["project_id"] == "ringgata-extension-demo"
        ]
        self.assertEqual(len(changed), 1)
        self.assertIn("2026-11-17", changed[0]["message"])
        self.assertIn("2026-11-24", changed[0]["message"])
        self.assertEqual(
            {alert["id"] for alert in first["alerts"]},
            {alert["id"] for alert in second["alerts"]},
        )

    def test_expired_end_is_unconfirmed_without_explicit_source(self):
        result = self.check()
        unconfirmed = [
            alert for alert in result["alerts"]
            if alert["kind"] == "reopening_unconfirmed"
            and alert["project_id"] == "ringgata-expired-demo"
        ]
        self.assertEqual(len(unconfirmed), 1)
        self.assertEqual(
            unconfirmed[0]["message"],
            "Scheduled end passed; reopening unconfirmed.",
        )

    def test_post_end_alerts_are_restricted_to_affected_journeys(self):
        affected = saved_journey()
        unrelated = unrelated_saved_journey(self.workspace)
        previous = [
            {
                key: project.get(key)
                for key in (
                    "id", "start_date", "end_date", "section_ids",
                    "reopening_confirmed", "reopening_confirmed_at",
                )
            }
            for project in self.base["projects"]
        ]
        result = build_alerts(
            self.workspace,
            ROOT,
            [affected, unrelated],
            previous,
            "current",
            "2026-11-18",
        )
        post_end_kinds = {"dates_changed", "reopening_confirmed", "reopening_unconfirmed"}
        post_end = [
            alert for alert in result["alerts"] if alert["kind"] in post_end_kinds
        ]
        self.assertTrue(post_end)
        self.assertTrue(all(
            alert["journey_id"] == affected["id"] for alert in post_end
        ))
        self.assertFalse(any(
            alert["journey_id"] == unrelated["id"] for alert in post_end
        ))
        self.assertTrue(all(alert.get("route_effect") for alert in post_end))

    def test_post_end_association_uses_modeled_project_impact(self):
        result = build_alerts(
            self.workspace,
            ROOT,
            [saved_journey()],
            [],
            "current",
            "2026-11-18",
        )
        unconfirmed = next(
            alert for alert in result["alerts"]
            if alert["kind"] == "reopening_unconfirmed"
        )
        self.assertEqual(unconfirmed["route_effect"]["status"], "longer")
        self.assertEqual(unconfirmed["route_effect"]["baseline_metres"], 1384)
        self.assertEqual(unconfirmed["route_effect"]["metres"], 2086)

    def test_reopening_requires_explicit_confirmation(self):
        result = self.check()
        confirmed = [
            alert for alert in result["alerts"]
            if alert["kind"] == "reopening_confirmed"
        ]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["project_id"], "ringgata-reopened-demo")
        self.assertNotEqual(
            confirmed[0]["id"],
            next(
                alert["id"] for alert in result["alerts"]
                if alert["kind"] == "reopening_unconfirmed"
            ),
        )

    def test_unavailable_journey_or_project_is_reported(self):
        journey = saved_journey()
        journey["case_id"] = "missing-case"
        result = build_alerts(
            self.workspace, ROOT, [journey], [], "current", "2026-11-18"
        )
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["unavailable"][0]["kind"], "journey_unavailable")

        snapshot = json.loads(json.dumps(self.current))
        snapshot["projects"][0]["section_ids"] = ["missing-section"]
        with patch("project_alerts.load_snapshot", return_value=snapshot):
            result = self.check()
        self.assertTrue(result["unavailable"])
        self.assertEqual(result["unavailable"][0]["kind"], "project_unavailable")

        invalid = json.loads(json.dumps(self.current))
        invalid["projects"][0].pop("source_url")
        with patch("project_alerts.json.loads", return_value=invalid):
            with self.assertRaisesRegex(ValueError, "invalid"):
                load_snapshot(ROOT, "current")

    def test_client_persists_deduplication_and_dismissal_state(self):
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "workspace" / "index.html").read_text(encoding="utf-8")
        engine = (ROOT / "harness" / "project_alerts.py").read_text(encoding="utf-8")
        self.assertIn("hamar-access-lab.journey-alert-state.v1", script)
        self.assertIn("dismissedJourneyAlerts", script)
        self.assertIn('id="refresh-journey-alerts"', html)
        self.assertIn("Checks occur when the app opens or when you refresh", script)
        self.assertIn("Scheduled end passed; reopening unconfirmed", engine)
        self.assertIn("Reopening confirmed", script)

    def test_confirmed_koigen_simulation_matches_only_affected_journey(self):
        preset = self.workspace.case_payload("koigen-demo")["journeys"][0]
        affected = {
            "id": "koigen-walk", "name": "Koigen walk", "case_id": "koigen-demo",
            "origin": preset["origin"], "destination": preset["destination"],
        }
        unrelated = unrelated_saved_journey(self.workspace)
        scenario = self.workspace.monitor_scenario(koigen_monitor_request())
        self.assertEqual(scenario["id"], self.workspace.monitor_scenario(koigen_monitor_request())["id"])
        payload = {"saved_journeys": [affected, unrelated], "previous_projects": [],
                   "monitor_scenario": json.loads(json.dumps(scenario)), "as_of": "2026-11-18"}
        first = self.workspace.journey_alerts(payload)
        second = self.workspace.journey_alerts(payload)
        simulated = [a for a in first["alerts"] if a["user_confirmed_simulation"]]
        self.assertEqual(len(simulated), 1)
        alert = simulated[0]
        self.assertEqual(alert["journey_id"], affected["id"])
        self.assertEqual((alert["route_effect"]["baseline_metres"], alert["route_effect"]["metres"]),
                         (323, 593))
        self.assertEqual(alert["id"], next(
            a["id"] for a in second["alerts"] if a["user_confirmed_simulation"]
        ))
        self.assertTrue(alert["checked_at"])
        self.assertEqual(alert["source"]["project_source_url"], scenario["source"]["url"])
        self.assertIsNone(scenario["source"]["footpath_dates"])
        self.assertTrue(scenario["confirmation"]["confirmed"])

        payload["as_of"] = "2026-11-19"
        expired = [a for a in self.workspace.journey_alerts(payload)["alerts"]
                   if a["user_confirmed_simulation"]]
        self.assertEqual([a["kind"] for a in expired], ["reopening_unconfirmed"])
        self.assertEqual(expired[0]["message"], "Simulation period ended; reopening unconfirmed.")

    def test_monitor_scenario_rejects_unconfirmed_or_tampered_records(self):
        request = koigen_monitor_request()
        request["modeled_section_confirmation"] = False
        with self.assertRaisesRegex(ValueError, "explicitly confirm"):
            self.workspace.monitor_scenario(request)
        request = koigen_monitor_request()
        request["projects"][0]["sections"] = ["missing"]
        with self.assertRaises(ValueError):
            self.workspace.monitor_scenario(request)
        request = koigen_monitor_request()
        request["projects"][0]["end_date"] = "2026-11-17"
        with self.assertRaisesRegex(ValueError, "before start"):
            self.workspace.monitor_scenario(request)
        scenario = self.workspace.monitor_scenario(koigen_monitor_request())
        scenario["source"]["footpath_dates"] = "2026-11-18"
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.workspace.journey_alerts({"saved_journeys": [], "previous_projects": [],
                                           "monitor_scenario": scenario})


class JourneyAlertHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = hamar_workspace.WorkspaceServer(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_alert_endpoint_and_saved_record_revision(self):
        base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        with urllib.request.urlopen(
            base_url + "/api/project-records?revision=base"
        ) as response:
            base = json.load(response)
        self.assertTrue(base["synthetic"])
        self.assertEqual(base["projects"][1]["end_date"], "2026-11-17")
        request = urllib.request.Request(
            base_url + "/api/journey-alerts",
            data=json.dumps({
                "saved_journeys": [saved_journey()],
                "previous_projects": base["projects"],
                "as_of": "2026-11-18",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        self.assertTrue(any(
            alert["kind"] == "dates_changed" for alert in result["alerts"]
        ))
        self.assertEqual(
            result["snapshot"]["sha256"],
            self.server.workspace.project_records()["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
