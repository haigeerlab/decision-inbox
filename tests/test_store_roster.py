import unittest

from helpers import TempHomeTestCase

from decision_inbox import store

HUB = {"relayName": "hub-claude", "shortName": "收件枢纽", "role": "hub",
       "line": [], "host": "claude-desktop"}
DEV = {"relayName": "fe-codex", "shortName": "前端", "role": "dev",
       "line": ["前端"], "host": "codex-desktop", "repo": "/tmp/shop-fe"}
OWNER = {"relayName": "fe-owner", "shortName": "前端负责人", "role": "owner",
         "line": ["前端", "UI"], "host": "claude-desktop"}


class RosterTest(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        with self.g.transaction() as tx:
            for s in (HUB, DEV, OWNER):
                tx.add_session(dict(s))

    def test_roster_lookup(self):
        self.assertEqual([s["relayName"] for s in store.roster(self.g)],
                         ["hub-claude", "fe-codex", "fe-owner"])
        self.assertEqual(store.find_session(self.g, relay_name="fe-codex")["shortName"], "前端")
        self.assertEqual(store.find_session(self.g, short_name="前端负责人")["role"], "owner")
        self.assertIsNone(store.find_session(self.g, short_name="后台"))

    def test_desktop_session(self):
        with self.g.transaction() as tx:
            tx.add_session(dict(OWNER, relayName="api-owner", shortName="API负责人", line=["API"],
                                desktopSession="local_0db22e7e-6836-46bc-9e37-7a82d8f09bb9"))
        self.assertEqual(store.find_session(self.g, relay_name="api-owner")["desktopSession"],
                         "local_0db22e7e-6836-46bc-9e37-7a82d8f09bb9")
        self.assertNotIn("desktopSession", store.find_session(self.g, relay_name="fe-owner"))
        for bad in ("0db22e7e", "", 12, None, "local_"):
            with self.subTest(bad=bad):
                with self.assertRaises(store.InvalidSession):
                    with self.g.transaction() as tx:
                        tx.add_session(dict(OWNER, relayName="x-owner", shortName="X负责人", line=["X"],
                                            desktopSession=bad))
        self.assertIsNone(store.find_session(self.g, relay_name="x-owner"))

    def test_crew_coordinator_and_local_rules_flags(self):
        """crew-coordinator-seam: booleans only; the coordinator flag on dev lines, local rules on Claude."""
        coord = dict(DEV, relayName="crew-coord", shortName="前端并行", host="claude-desktop",
                     crewCoordinator=True, localRules=True)
        with self.g.transaction() as tx:
            tx.add_session(coord)
        self.assertTrue(store.find_session(self.g, relay_name="crew-coord")["crewCoordinator"])
        bad_entries = [dict(coord, relayName="b1", shortName="b1", crewCoordinator="yes"),
                       dict(coord, relayName="b2", shortName="b2", localRules=1),
                       dict(OWNER, relayName="b3", shortName="b3", crewCoordinator=True),
                       dict(DEV, relayName="b4", shortName="b4", localRules=True)]
        for bad in bad_entries:
            with self.subTest(bad=bad["relayName"]):
                with self.assertRaises(store.InvalidSession):
                    with self.g.transaction() as tx:
                        tx.add_session(bad)

    def test_legacy_format_flag(self):
        """transition-compat: booleans only, dev lines only."""
        with self.g.transaction() as tx:
            tx.add_session(dict(DEV, relayName="old-fe", shortName="旧前端", legacyFormat=True))
        self.assertTrue(store.find_session(self.g, relay_name="old-fe")["legacyFormat"])
        for bad in (dict(DEV, relayName="b1", shortName="b1", legacyFormat="yes"),
                    dict(OWNER, relayName="b2", shortName="b2", legacyFormat=True)):
            with self.subTest(bad=bad["relayName"]):
                with self.assertRaises(store.InvalidSession):
                    with self.g.transaction() as tx:
                        tx.add_session(bad)

    def test_replace_existing_entry(self):
        with self.g.transaction() as tx:
            tx.replace_session(dict(DEV, repo="/tmp/shop-fe-2"))
        self.assertEqual(len(store.roster(self.g)), 3)
        self.assertEqual(store.find_session(self.g, relay_name="fe-codex")["repo"], "/tmp/shop-fe-2")

    def test_invalid_entries_rejected_and_roster_unchanged(self):
        before = (self.g.path / "roster.json").read_bytes()
        bad = {
            "duplicate relay name": dict(DEV, shortName="API"),
            "duplicate short name": dict(DEV, relayName="api-codex"),
            "second hub": dict(HUB, relayName="hub-2", shortName="枢纽二"),
            "hub on codex": dict(HUB, host="codex-desktop"),
            "dev without line": dict(DEV, relayName="x", shortName="X", line=[]),
            "dev with two lines": dict(DEV, relayName="x", shortName="X", line=["a", "b"]),
            "dev without repo": {k: v for k, v in dict(DEV, relayName="x", shortName="X").items() if k != "repo"},
            "relative repo": dict(DEV, relayName="x", shortName="X", repo="shop"),
            "owner without line": dict(OWNER, relayName="x", shortName="X", line=[]),
            "coordinator with line": {"relayName": "x", "shortName": "总协调", "role": "coordinator",
                                      "line": ["前端"], "host": "codex-desktop"},
            "unknown role": dict(DEV, relayName="x", shortName="X", role="observer"),
            "unknown host": dict(DEV, relayName="x", shortName="X", host="cli"),
            "short name too long": dict(DEV, relayName="x", shortName="一二三四五六七八九十十一十二十三"),
            "empty relay name": dict(DEV, relayName="", shortName="X"),
        }
        for label, entry in bad.items():
            with self.subTest(label):
                with self.assertRaises(store.InvalidSession):
                    with self.g.transaction() as tx:
                        tx.add_session(entry)
        with self.assertRaises(store.InvalidSession):
            with self.g.transaction() as tx:
                tx.replace_session(dict(DEV, relayName="nobody", shortName="无人"))
        with self.assertRaises(store.InvalidSession):
            with self.g.transaction() as tx:
                tx.replace_session(dict(DEV, shortName="收件枢纽"))
        self.assertEqual((self.g.path / "roster.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
