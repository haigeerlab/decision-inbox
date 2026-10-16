import json
import os
import shutil
import subprocess
import unittest

from helpers import REPO, TempHomeTestCase

from decision_inbox import onboard, store, tickets

NOW = "2026-10-17T01:00:00Z"
HUB_DESKTOP = "local_00000000-0000-0000-0000-00000000hub0"


def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def hook_commands(event):
    return [h["command"] for block in load("hooks/hooks.json")["hooks"][event] for h in block["hooks"]]


class ManifestTest(unittest.TestCase):
    def test_names_and_versions(self):
        claude, codex = load(".claude-plugin/plugin.json"), load(".codex-plugin/plugin.json")
        market = load(".claude-plugin/marketplace.json")
        self.assertEqual((claude["name"], codex["name"]), ("decision-inbox", "decision-inbox"))
        self.assertEqual(claude["version"], codex["version"])
        self.assertEqual(claude["version"], "0.0.2")
        self.assertEqual((codex["skills"], codex["hooks"]), ("./skills/", "./hooks/hooks.json"))
        self.assertEqual(market["name"], "decision-inbox-marketplace")
        self.assertEqual([(p["name"], p["source"]) for p in market["plugins"]], [("decision-inbox", "./")])

    def test_hooks_file(self):
        hooks = load("hooks/hooks.json")["hooks"]
        self.assertEqual(set(hooks), {"Stop", "SessionStart"})
        for event in hooks:
            for command in hook_commands(event):
                self.assertNotIn("--group", command)
                self.assertIn("PLUGIN_ROOT", command)
                self.assertIn("CLAUDE_PLUGIN_ROOT", command)

    def test_entry_script_is_executable(self):
        self.assertTrue(os.access(REPO / "bin" / "decision-inbox", os.X_OK))


class HookCommandTest(TempHomeTestCase):
    """Run the exact command strings from hooks.json against a copy of the plugin."""

    def setUp(self):
        super().setUp()
        self.plugin = self.home / "plugin-copy"
        for part in ("bin", "decision_inbox", "hooks"):
            shutil.copytree(REPO / part, self.plugin / part,
                            ignore=shutil.ignore_patterns("__pycache__"), symlinks=True)

    def run_hook(self, event, stdin="", **env):
        base = {k: v for k, v in os.environ.items() if k not in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")}
        base.update({"DECISION_INBOX_HOME": str(self.home), **env})
        (command,) = hook_commands(event)
        return subprocess.run(["/bin/sh", "-c", command], input=stdin, capture_output=True, text=True,
                              env=base, cwd=self.home, timeout=60)

    def test_without_plugin_root_passes_quietly(self):
        for event in ("Stop", "SessionStart"):
            done = self.run_hook(event, stdin="{}")
            self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_session_start_refreshes_shim(self):
        for var in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
            shim = self.home / "bin" / "decision-inbox"
            if shim.exists():
                shim.write_text("old", encoding="utf-8")
            done = self.run_hook("SessionStart", **{var: str(self.plugin)})
            self.assertEqual((done.returncode, done.stdout), (0, ""))
            self.assertIn(str(self.plugin / "bin" / "decision-inbox"), shim.read_text(encoding="utf-8"))

    def test_session_start_without_home_does_nothing(self):
        missing = self.home / "absent"
        done = self.run_hook("SessionStart", PLUGIN_ROOT=str(self.plugin), DECISION_INBOX_HOME=str(missing))
        self.assertEqual(done.returncode, 0)
        self.assertFalse(missing.exists())

    def test_stop_blocks_then_passes(self):
        fe, api, hub_dir = (self.home / n for n in ("fe", "api", "hub"))
        for d in (fe, api, hub_dir):
            d.mkdir()
        onboard.hub("demo", "di-hub", HUB_DESKTOP, hub_dir, True, NOW)
        onboard.join("demo", "dev", "fe-codex", "前端", "codex-desktop", ["前端"], None, fe, None, [], True, NOW)
        onboard.join("demo", "dev", "api-codex", "API", "codex-desktop", ["API"], None, api, None, [], True, NOW)
        tickets.receive(store.open_group("demo"), "【等待其他会话】\n结束：无\n在等谁：前端\n等什么：Mock 数据\n",
                        sender="api-codex", relay_id=1, sent_at=NOW)
        first = self.run_hook("Stop", stdin=json.dumps({"cwd": str(fe), "stop_hook_active": False}),
                              CLAUDE_PLUGIN_ROOT=str(self.plugin))
        self.assertEqual(first.returncode, 0)
        self.assertEqual(json.loads(first.stdout)["decision"], "block")
        second = self.run_hook("Stop", stdin=json.dumps({"cwd": str(fe), "stop_hook_active": True}),
                               PLUGIN_ROOT=str(self.plugin))
        self.assertEqual((second.returncode, second.stdout), (0, ""))

    def test_stop_with_broken_input_passes(self):
        done = self.run_hook("Stop", stdin="not json", PLUGIN_ROOT=str(self.plugin))
        self.assertEqual((done.returncode, done.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
