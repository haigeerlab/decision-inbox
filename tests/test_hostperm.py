"""host-permission-check (R21 DI-4): read the host's real permissions, compare with what the Plan needs."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from decision_inbox import hostperm


class HostCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="di-host-"))
        self.repo = self.tmp / "work" / "app"
        self.repo.mkdir(parents=True)
        self.config = self.tmp / "codex-config.toml"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def global_config(self, text):
        self.config.write_text(text, encoding="utf-8")

    def project_config(self, text):
        (self.repo / ".codex").mkdir(exist_ok=True)
        (self.repo / ".codex" / "config.toml").write_text(text, encoding="utf-8")

    def trust(self, path):
        return f'[projects."{path}"]\ntrust_level = "trusted"\n'

    def snapshot(self):
        return {p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file()}


class CodexFactsTest(HostCase):
    def test_global_off_no_project_config(self):
        self.global_config('sandbox_mode = "workspace-write"\n')
        f = hostperm.codex_facts(str(self.repo), self.config)
        self.assertEqual((f.write, f.network, f.trusted), (True, False, False))

    def test_trusted_project_config_turns_network_on(self):
        self.global_config('sandbox_mode = "workspace-write"\n\n' + self.trust(self.repo))
        self.project_config("[sandbox_workspace_write]\nnetwork_access = true\n")
        f = hostperm.codex_facts(str(self.repo), self.config)
        self.assertEqual((f.network, f.trusted, f.network_source), (True, True, "项目配置"))

    def test_trusted_parent_counts(self):
        self.global_config('sandbox_mode = "workspace-write"\n\n' + self.trust(self.tmp / "work"))
        self.project_config("[sandbox_workspace_write]\nnetwork_access = true\n")
        self.assertTrue(hostperm.codex_facts(str(self.repo), self.config).network)

    def test_untrusted_project_config_does_not_count(self):
        self.global_config('sandbox_mode = "workspace-write"\n')
        self.project_config("[sandbox_workspace_write]\nnetwork_access = true\n")
        f = hostperm.codex_facts(str(self.repo), self.config)
        self.assertEqual((f.network, f.trusted), (False, False))

    def test_global_network_and_full_access(self):
        self.global_config('sandbox_mode = "workspace-write"\n[sandbox_workspace_write]\nnetwork_access = true\n')
        self.assertEqual(hostperm.codex_facts(str(self.repo), self.config).network_source, "全局配置")
        self.global_config('sandbox_mode = "danger-full-access"\n')
        f = hostperm.codex_facts(str(self.repo), self.config)
        self.assertEqual((f.write, f.network), (True, True))

    def test_read_only(self):
        self.global_config('sandbox_mode = "read-only"\n')
        f = hostperm.codex_facts(str(self.repo), self.config)
        self.assertEqual((f.write, f.network), (False, False))

    def test_unreadable_or_unset(self):
        f = hostperm.codex_facts(str(self.repo), self.config)  # no file
        self.assertIsNone(f.network)
        self.assertIn("读不到", f.reason)
        self.global_config('model = "x"\n')
        f = hostperm.codex_facts(str(self.repo), self.config)
        self.assertIsNone(f.network)
        self.assertIn("sandbox_mode", f.reason)

    def test_reads_only(self):
        self.global_config('sandbox_mode = "workspace-write"\n\n' + self.trust(self.repo))
        self.project_config("[sandbox_workspace_write]\nnetwork_access = true\n")
        before = self.snapshot()
        hostperm.codex_facts(str(self.repo), self.config)
        self.assertEqual(self.snapshot(), before)


class ClaudeFactsTest(HostCase):
    def settings(self, name, doc):
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude" / name).write_text(json.dumps(doc), encoding="utf-8")

    def test_allowed_and_retired(self):
        self.assertFalse(hostperm.claude_facts(str(self.repo)).installs_allowed)
        self.settings("settings.local.json", {"permissions": {"allow": ["Bash(npm ci)"], "ask": ["Bash(npm install *)"]}})
        f = hostperm.claude_facts(str(self.repo))
        self.assertEqual((f.installs_allowed, f.retired), (True, ["Bash(npm install *)"]))

    def test_shared_settings_count_and_bad_json(self):
        self.settings("settings.json", {"permissions": {"allow": ["Bash(pip install -r *)"]}})
        self.assertTrue(hostperm.claude_facts(str(self.repo)).installs_allowed)
        (self.repo / ".claude" / "settings.local.json").write_text("{bad", encoding="utf-8")
        f = hostperm.claude_facts(str(self.repo))
        self.assertIsNone(f.installs_allowed)
        self.assertIn("settings.local.json", f.reason)


class PlanNeedsTest(HostCase):
    def plan(self, text, module="m"):
        d = self.repo / "tasks" / module
        d.mkdir(parents=True, exist_ok=True)
        (d / "plan.md").write_text(text, encoding="utf-8")

    def test_field_line(self):
        self.plan("# Plan\n\n需要的外部条件：无（不装依赖、不联网）。\n\n## Overview\n")
        self.assertEqual(hostperm.plan_needs(str(self.repo), "m"), "none")
        self.plan("# Plan\n\n需要的外部条件：从官方源装 vitest\n  以及联网拉取 schema\n\n## Overview\n")
        self.assertEqual(hostperm.plan_needs(str(self.repo), "m"), "needs")

    def test_section_heading(self):
        self.plan("# Plan\n\n## 需要的外部条件\n\n- 依赖：zod@3\n- 联网：npm 官方源\n\n## Tasks\n")
        self.assertEqual(hostperm.plan_needs(str(self.repo), "m"), "needs")
        self.plan("# Plan\n\n## 需要的外部条件\n\n无\n\n## Tasks\n")
        self.assertEqual(hostperm.plan_needs(str(self.repo), "m"), "none")

    def test_unknown(self):
        self.assertEqual(hostperm.plan_needs(str(self.repo), None), "unknown")
        self.assertEqual(hostperm.plan_needs(str(self.repo), "m"), "unknown")  # no file
        self.plan("# Plan\n\n## Overview\n")
        self.assertEqual(hostperm.plan_needs(str(self.repo), "m"), "unknown")


class CompareTest(HostCase):
    def codex(self, network, trusted=True):
        return hostperm.CodexFacts(write=True, network=network, trusted=trusted,
                                   network_source="全局配置" if network else "", reason=None)

    def test_codex_bad_gives_both_options(self):
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False), None, "needs")
        self.assertEqual(r.state, "bad")
        for words in (".codex/config.toml", "[sandbox_workspace_write]", "network_access = true", "没实测",
                      "不改 ~/.codex/config.toml", "B ", "去会话操作"):
            self.assertIn(words, r.fix)

    def test_untrusted_starts_with_trust(self):
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False, trusted=False), None, "needs")
        self.assertIn("先在 Codex 里信任这个项目", r.fix)

    def test_ok_and_cannot_compare(self):
        self.assertEqual(hostperm.compare("codex-desktop", str(self.repo), self.codex(True), None, "needs").state, "ok")
        self.assertEqual(hostperm.compare("codex-desktop", str(self.repo), self.codex(False), None, "none").state, "ok")
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False), None, "unknown")
        self.assertEqual(r.state, "ok")
        self.assertIn("没法对照", r.evidence)

    def test_unknown_facts(self):
        facts = hostperm.CodexFacts(write=None, network=None, trusted=None, network_source="", reason="读不到 x")
        r = hostperm.compare("codex-desktop", str(self.repo), facts, None, "needs")
        self.assertEqual((r.state, r.evidence), ("unknown", "读不到 x"))

    def test_claude(self):
        bad = hostperm.ClaudeFacts(installs_allowed=False, retired=[], reason=None)
        r = hostperm.compare("claude-desktop", str(self.repo), None, bad, "needs")
        self.assertEqual(r.state, "bad")
        self.assertIn("重跑接入", r.fix)
        old = hostperm.ClaudeFacts(installs_allowed=True, retired=["Bash(npm install *)"], reason=None)
        self.assertEqual(hostperm.compare("claude-desktop", str(self.repo), None, old, "needs").state, "bad")
        good = hostperm.ClaudeFacts(installs_allowed=True, retired=[], reason=None)
        self.assertEqual(hostperm.compare("claude-desktop", str(self.repo), None, good, "needs").state, "ok")


if __name__ == "__main__":
    unittest.main()
