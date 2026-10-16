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
        self.assertEqual(fe.presence_detail, "permission prompt")
        self.assertIsNone(owner.presence_detail)

    def test_presence_detail_blank_is_none(self):
        for presence in ({"state": "waiting-approval", "detail": ""}, {"state": "waiting-approval"}, None):
            with self.subTest(presence=presence):
                agent = {"name": "x", "host": None, "unread": 0, "lastActivity": "t", "wake": None}
                if presence is not None:
                    agent["presence"] = presence
                snap = relay.parse_agents(json.dumps({"agents": [agent]}))
                self.assertIsNone(snap.agents["x"].presence_detail)

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


class VersionTest(unittest.TestCase):
    def test_oldest_at_means_ok(self):
        snap = relay.parse_agents(fixture("agents-0.6.10.json"))
        self.assertEqual(snap.relay_status, "ok")
        self.assertEqual(snap.agents["hub-claude"].waiting_count, 0)

    def test_broadcast_unread_without_waiting_is_not_too_old(self):
        doc = json.loads(fixture("agents-0.6.10.json"))
        doc["agents"][0]["unread"] = 2  # hub-claude: unread broadcasts, no waiting
        snap = relay.parse_agents(json.dumps(doc))
        self.assertEqual(snap.relay_status, "ok")
        self.assertEqual(snap.agents["hub-claude"].waiting_count, 0)
        self.assertFalse(any(relay.UPGRADE_HINT in w for w in snap.warnings))

    def test_explicit_old_version(self):
        snap = relay.parse_agents(fixture("agents-0.6.10.json"), relay_version="0.6.1")
        self.assertEqual(snap.relay_status, "too-old")
        self.assertIn(relay.UPGRADE_HINT, snap.warnings)
        for agent in snap.agents.values():
            if agent.host_app == "claude":
                self.assertIsNone(agent.waiting_count, agent.name)
        self.assertEqual(snap.agents["fe-codex"].waiting_count, 0)

    def test_undetermined_without_any_waiting(self):
        snap = relay.parse_agents(fixture("agents-empty.json"))
        self.assertEqual(snap.relay_status, "undetermined")
        self.assertIsNone(snap.agents["hub-claude"].waiting_count)
        self.assertEqual(snap.agents["fe-codex"].waiting_count, 0)
        snap = relay.parse_agents(fixture("agents-empty.json"), relay_version="0.6.10")
        self.assertEqual(snap.relay_status, "ok")
        self.assertEqual(snap.agents["hub-claude"].waiting_count, 0)

    def test_newer_version_and_bad_version_string(self):
        self.assertEqual(relay.parse_agents(fixture("agents-empty.json"), relay_version="0.10.0").relay_status, "ok")
        snap = relay.parse_agents(fixture("agents-empty.json"), relay_version="v0.6")
        self.assertEqual(snap.relay_status, "undetermined")
        self.assertTrue(any("版本号看不懂" in w for w in snap.warnings))


class ParseOutboxTest(unittest.TestCase):
    def test_delivery_facts(self):
        out = relay.parse_outbox(fixture("outbox-0.6.10.json"), sender="hub-claude")
        self.assertEqual(out.sender, "hub-claude")
        self.assertEqual([m.id for m in out.messages], [120, 118])
        queued, accepted = out.messages
        self.assertEqual(queued.sender, "hub-claude")
        self.assertEqual(queued.recipient, "owner-claude")
        self.assertEqual(queued.sent_at, "2026-10-16T05:01:00.000Z")
        self.assertEqual(queued.delivery_state, "queued")
        self.assertIsNone(queued.acknowledged_at)
        self.assertEqual(queued.expires_at, "2026-10-17T05:01:00.000Z")
        self.assertEqual(queued.reply_to, 109)
        self.assertEqual(queued.reply_ids, ())
        self.assertEqual(accepted.delivery_state, "accepted")
        self.assertEqual(accepted.acknowledged_at, "2026-10-16T04:55:00.000Z")
        self.assertIsNone(accepted.expires_at)
        self.assertEqual(accepted.reply_ids, (119, 121))

    def test_preview_never_reaches_output(self):
        out = relay.parse_outbox(fixture("outbox-0.6.10.json"), sender="hub-claude")
        self.assertNotIn("SECRET", repr(out))

    def test_entry_without_id_skipped_with_warning(self):
        out = relay.parse_outbox(fixture("outbox-0.6.10.json"), sender="hub-claude")
        self.assertEqual(len(out.messages), 2)
        self.assertTrue(any("id" in w for w in out.warnings))

    def test_structural_errors(self):
        for bad in ("nope", '{"agent": "x"}', '{"entries": 3}'):
            with self.subTest(bad=bad):
                with self.assertRaises(relay.RelayDataError):
                    relay.parse_outbox(bad, sender="x")


class WakeStatusTest(unittest.TestCase):
    def test_message_status(self):
        st = relay.parse_message_status(fixture("message-status.json"))
        self.assertEqual((st.id, st.sender, st.recipient), (2842, "fe-codex", "hub"))
        self.assertEqual(st.sent_at, "2026-10-16T03:10:00.000Z")
        self.assertEqual(st.delivery_state, "accepted")
        self.assertEqual(st.acknowledged_at, "2026-10-16T03:12:00.000Z")
        self.assertEqual(st.reply_ids, (2850, 2851))
        self.assertEqual((st.wake_state, st.wake_detail), ("acknowledged", "Recipient acknowledged the message"))
        self.assertEqual(st.outcome, "replied")
        self.assertNotIn("preview", repr(st))
        self.assertNotIn("正文预览", repr(st))

    def test_message_status_without_wake_or_optional_fields(self):
        doc = {"message": {"id": 9, "fromAgent": "hub", "toAgent": "api-codex"}, "wake": None}
        st = relay.parse_message_status(json.dumps(doc))
        self.assertEqual((st.id, st.delivery_state, st.acknowledged_at, st.reply_ids), (9, None, None, ()))
        self.assertEqual((st.wake_state, st.wake_detail, st.outcome, st.sent_at), (None, None, None, None))

    def test_message_status_structural_errors(self):
        for text in ("not json", "[]", json.dumps({"deliveryState": "accepted"}),
                     json.dumps({"message": {"fromAgent": "x"}})):
            with self.subTest(text=text):
                with self.assertRaises(relay.RelayDataError):
                    relay.parse_message_status(text)

    def test_wake_jobs_counts(self):
        jobs = [{"agent": "a", "state": "held"}, {"agent": "a", "state": "held"}, {"agent": "a", "state": "refused"},
                {"agent": "b", "state": "acknowledged"}, {"state": "held"}, "junk", {"agent": "c"}]
        counts = relay.parse_wake_jobs(json.dumps({"summary": {}, "jobs": jobs}))
        self.assertEqual(counts, {"a": {"held": 2, "refused": 1}, "b": {"acknowledged": 1}})
        with self.assertRaises(relay.RelayDataError):
            relay.parse_wake_jobs(json.dumps({"summary": {}}))
        with self.assertRaises(relay.RelayDataError):
            relay.parse_wake_jobs("{")


class RealCaptureTest(unittest.TestCase):
    """Sanitised output captured from agent-relay 0.6.10 on 2026-10-16."""

    def test_real_agents(self):
        snap = relay.parse_agents(fixture("real-agents.json"))
        self.assertEqual(snap.relay_status, "ok")
        self.assertEqual(snap.warnings, ())
        self.assertEqual(len(snap.agents), 12)
        busy = snap.agents["agent-6"]
        self.assertEqual(busy.waiting_count, 14)
        self.assertEqual(len(busy.waiting_ids), 14)
        self.assertEqual(busy.waiting_from, ("agent-8", "agent-9", "agent-4", "agent-3"))
        self.assertEqual(busy.waiting_oldest_at, "2026-10-13T08:40:43.388Z")
        self.assertEqual(busy.presence, "unknown")
        self.assertEqual(snap.agents["agent-1"].waiting_count, 0)
        self.assertEqual(snap.agents["agent-1"].presence, "active")
        self.assertEqual(snap.agents["agent-3"].presence, "active")
        self.assertFalse(snap.agents["agent-2"].wake_bound)

    def test_real_outbox(self):
        out = relay.parse_outbox(fixture("real-outbox.json"), sender="agent-3")
        self.assertEqual(out.warnings, ())
        self.assertEqual([m.id for m in out.messages], [2927, 2649, 2175, 2170, 2166])
        first = out.messages[0]
        self.assertEqual((first.recipient, first.delivery_state, first.reply_to), ("agent-4", "queued", 2916))
        self.assertTrue(all(m.delivery_state == "accepted" for m in out.messages[1:]))

    def test_real_wake_jobs(self):
        counts = relay.parse_wake_jobs(fixture("real-wake-jobs.json"))
        self.assertEqual(counts, {"agent-3": {"unknown": 1, "acknowledged": 1}, "agent-2": {"pending": 1, "read": 1},
                                  "agent-1": {"acknowledged": 1}})

    def test_real_fixtures_are_sanitised(self):
        jobs = json.loads(fixture("real-wake-jobs.json"))["jobs"]
        self.assertNotIn('"preview"', fixture("real-wake-jobs.json"))
        for job in jobs:
            for field in ("agent", "fromAgent"):
                self.assertRegex(job[field], r"^agent-\d+$")
            self.assertEqual(job["mailboxPath"], "/sanitized/mailbox.sqlite")
            self.assertRegex(job["target"]["sessionId"], r"^session-\d+$")
        for name in ("real-agents.json", "real-outbox.json"):
            doc = json.loads(fixture(name))
            text = json.dumps(doc, ensure_ascii=False)
            self.assertNotIn('"preview"', text, name)
            for key in ("agents", "entries"):
                for item in doc.get(key, []):
                    for field in ("name", "toAgent"):
                        if field in item:
                            self.assertRegex(item[field], r"^agent-\d+$", name)


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


class ParseInboxTest(unittest.TestCase):
    def test_page_fields(self):
        inbox = relay.parse_inbox(fixture("inbox.json"))
        self.assertEqual(inbox.agent, "di-hub")
        self.assertFalse(inbox.has_more)
        first = inbox.messages[0]
        self.assertEqual((first.id, first.sender, first.created_at, first.reply_to, first.expects_reply),
                         (4001, "fe-codex", "2026-10-16T08:00:00.000Z", None, True))
        self.assertEqual(first.body, "【等待用户】\n来自：前端\n要你决定：选方案")
        self.assertFalse(first.truncated)
        self.assertIsNone(first.next_offset)
        self.assertEqual(inbox.messages[1].sender, "bridge")
        self.assertEqual(inbox.messages[1].reply_to, 3990)

    def test_entries_without_id_or_sender_skipped_with_warning(self):
        inbox = relay.parse_inbox(fixture("inbox.json"))
        self.assertEqual([m.id for m in inbox.messages], [4001, 4002])
        self.assertEqual(len(inbox.warnings), 2)

    def test_truncated_body_and_more_pages(self):
        inbox = relay.parse_inbox(fixture("inbox-truncated.json"))
        self.assertTrue(inbox.has_more)
        m = inbox.messages[0]
        self.assertTrue(m.truncated)
        self.assertEqual(m.next_offset, 20)

    def test_single_message_read(self):
        doc = json.loads(fixture("inbox.json"))
        single = {"agent": "di-hub", "message": doc["messages"][0], "readRecorded": True}
        inbox = relay.parse_inbox(json.dumps(single, ensure_ascii=False))
        self.assertEqual([m.id for m in inbox.messages], [4001])
        self.assertFalse(inbox.has_more)

    def test_structural_errors(self):
        for text in ("not json", "[]", '{"agent": "x"}', '{"messages": {}}'):
            with self.assertRaises(relay.RelayDataError):
                relay.parse_inbox(text)
