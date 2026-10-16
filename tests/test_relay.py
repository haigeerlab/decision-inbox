import ast
import json
import unittest
from pathlib import Path

from helpers import REPO

from decision_inbox import relay

FIX = Path(__file__).resolve().parent / "fixtures" / "relay"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class ParseAgentsTest(unittest.TestCase):
    def test_fields_from_0_6_10(self):
        snap = relay.parse_agents(fixture("agents-0.6.10.json"))
        owner = snap.agents["owner-claude"]
        self.assertEqual(owner.host_app, "claude")
        self.assertEqual(owner.presence, "offline")
        self.assertEqual(owner.unread, 3)
        self.assertEqual(owner.waiting_count, 3)
        self.assertEqual(owner.waiting_from, ("fe-codex", "hub-claude"))
        self.assertEqual(owner.waiting_ids, (101, 105, 109))
        self.assertEqual(owner.waiting_oldest_at, "2026-10-16T03:10:00.000Z")
        self.assertEqual(owner.last_activity_at, "2026-10-16T03:00:00.000Z")
        self.assertTrue(owner.wake_bound)
        self.assertFalse(owner.retired)
        api = snap.agents["api-codex"]
        self.assertIsNone(api.host_app)
        self.assertFalse(api.wake_bound)
        fe = snap.agents["fe-codex"]
        self.assertEqual(fe.presence, "needs-user")
        self.assertEqual(fe.presence_raw, "waiting-approval")
        self.assertEqual(fe.presence_since, "2026-10-16T04:31:00.000Z")

    def test_presence_categories(self):
        cases = {"running": "active", "waiting-input": "needs-user", "waiting-approval": "needs-user",
                 "stopped": "offline", "unreachable": "unreachable", "unknown": "unknown",
                 None: "unknown", "something-new": "unknown"}
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                agent = {"name": "x", "host": None, "unread": 0, "lastActivity": "t", "wake": None}
                if raw is not None:
                    agent["presence"] = {"state": raw}
                snap = relay.parse_agents(json.dumps({"agents": [agent]}))
                self.assertEqual(snap.agents["x"].presence, want)
                self.assertEqual(snap.agents["x"].presence_raw, raw)

    def test_bodies_never_reach_output(self):
        snap = relay.parse_agents(fixture("agents-edge.json"))
        text = repr(snap) + repr(snap.agents)
        self.assertNotIn("SECRET", text)

    def test_entry_without_name_skipped_with_warning(self):
        snap = relay.parse_agents(fixture("agents-edge.json"))
        self.assertEqual(sorted(snap.agents), ["lost-claude", "old-claude", "ui-codex"])
        self.assertTrue(any("name" in w for w in snap.warnings))
        self.assertEqual(snap.agents["lost-claude"].presence, "unreachable")

    def test_retired_agent(self):
        snap = relay.parse_agents(fixture("agents-edge.json"))
        old = snap.agents["old-claude"]
        self.assertTrue(old.retired)
        self.assertEqual(old.waiting_count, 0)
        self.assertEqual(old.presence, "unknown")

    def test_structural_errors(self):
        for bad in ("not json", "[]", '{"count": 0}', '{"agents": {}}'):
            with self.subTest(bad=bad):
                with self.assertRaises(relay.RelayDataError):
                    relay.parse_agents(bad)


class StaticScanTest(unittest.TestCase):
    def test_no_network_or_subprocess_imports(self):
        banned = {"socket", "subprocess", "urllib", "http"}
        tree = ast.parse((REPO / "decision_inbox" / "relay.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                self.assertNotIn(name.split(".")[0], banned, name)


if __name__ == "__main__":
    unittest.main()
