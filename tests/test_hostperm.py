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

    def test_allowed_retired_and_dev(self):
        self.assertFalse(hostperm.claude_facts(str(self.repo)).installs_allowed)
        self.settings("settings.local.json", {"permissions": {"allow": ["Bash(npm ci)"], "ask": ["Bash(npm install *)"]}})
        f = hostperm.claude_facts(str(self.repo))
        self.assertEqual((f.installs_allowed, f.retired), (False, ["Bash(npm install *)"]))  # only lockfile installs
        self.settings("settings.local.json", {"permissions": {"allow": ["Bash(npm install *)", "Bash(pnpm dev)"]}})
        f = hostperm.claude_facts(str(self.repo))
        self.assertEqual((f.installs_allowed, f.retired, f.allow[-1]), (True, [], "Bash(pnpm dev)"))

    def test_shared_settings_count_and_bad_json(self):
        self.settings("settings.json", {"permissions": {"allow": ["Bash(pnpm add *)"]}})
        self.assertTrue(hostperm.claude_facts(str(self.repo)).installs_allowed)
        (self.repo / ".claude" / "settings.local.json").write_text("{bad", encoding="utf-8")
        f = hostperm.claude_facts(str(self.repo))
        self.assertIsNone(f.installs_allowed)
        self.assertIn("settings.local.json", f.reason)


class ProjectNeedsTest(HostCase):
    def test_manifests(self):
        self.assertEqual(hostperm.project_needs(str(self.repo)), hostperm.ProjectNeeds(False, None))
        for name in ("pyproject.toml", "requirements-dev.txt", "uv.lock", "package.json"):
            with self.subTest(name=name):
                (self.repo / name).write_text("{}", encoding="utf-8")
                self.assertTrue(hostperm.project_needs(str(self.repo)).installs)
                (self.repo / name).unlink()

    def test_dev_script(self):
        (self.repo / "package.json").write_text('{"scripts": {"dev": "vite"}}', encoding="utf-8")
        (self.repo / "pnpm-lock.yaml").write_text("", encoding="utf-8")
        self.assertEqual(hostperm.project_needs(str(self.repo)), hostperm.ProjectNeeds(True, "Bash(pnpm dev)"))

    def test_plan_is_not_read(self):
        (self.repo / "tasks" / "m").mkdir(parents=True)
        (self.repo / "tasks" / "m" / "plan.md").write_text("需要的外部条件：装 vitest\n", encoding="utf-8")
        self.assertFalse(hostperm.project_needs(str(self.repo)).installs)
        self.assertFalse(hasattr(hostperm, "plan_needs"))


class CompareTest(HostCase):
    def codex(self, network, trusted=True):
        return hostperm.CodexFacts(write=True, network=network, trusted=trusted,
                                   network_source="全局配置" if network else "", reason=None)

    def needs(self, installs=True, dev=None):
        return hostperm.ProjectNeeds(installs, dev)

    def test_codex_bad_gives_both_options(self):
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False), None, self.needs())
        self.assertEqual(r.state, "bad")
        self.assertIn("依赖清单", r.evidence)
        for words in (".codex/config.toml", "[sandbox_workspace_write]", "network_access = true", "没实测",
                      "不改 ~/.codex/config.toml", "B ", "去会话操作"):
            self.assertIn(words, r.fix)

    def test_untrusted_starts_with_trust(self):
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False, trusted=False), None, self.needs())
        self.assertIn("先在 Codex 里信任这个项目", r.fix)

    def test_ok_cases(self):
        self.assertEqual(hostperm.compare("codex-desktop", str(self.repo), self.codex(True), None, self.needs()).state, "ok")
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False), None, self.needs(False))
        self.assertEqual(r.state, "ok")
        self.assertIn("没有依赖清单", r.evidence)

    def test_codex_dev_server_mentions_the_browser(self):
        r = hostperm.compare("codex-desktop", str(self.repo), self.codex(False), None, self.needs(dev="Bash(npm run dev)"))
        self.assertEqual(r.state, "bad")
        self.assertIn("可能下载不了浏览器", r.evidence)
        self.assertIn("A 你自己改", r.fix)
        self.assertNotIn("浏览器", hostperm.compare("codex-desktop", str(self.repo), self.codex(True), None,
                                                    self.needs(dev="Bash(npm run dev)")).evidence)

    def test_unknown_facts(self):
        facts = hostperm.CodexFacts(write=None, network=None, trusted=None, network_source="", reason="读不到 x")
        r = hostperm.compare("codex-desktop", str(self.repo), facts, None, self.needs())
        self.assertEqual((r.state, r.evidence), ("unknown", "读不到 x"))

    def test_claude(self):
        bad = hostperm.ClaudeFacts(installs_allowed=False, retired=[], reason=None)
        r = hostperm.compare("claude-desktop", str(self.repo), None, bad, self.needs())
        self.assertEqual(r.state, "bad")
        self.assertIn("重跑接入", r.fix)
        old = hostperm.ClaudeFacts(installs_allowed=True, retired=["Bash(npm install *)"], reason=None)
        self.assertEqual(hostperm.compare("claude-desktop", str(self.repo), None, old, self.needs()).state, "bad")
        good = hostperm.ClaudeFacts(installs_allowed=True, retired=[], reason=None)
        self.assertEqual(hostperm.compare("claude-desktop", str(self.repo), None, good, self.needs()).state, "ok")
        self.assertEqual(hostperm.compare("claude-desktop", str(self.repo), None, bad, self.needs(False)).state, "ok")

    def test_claude_dev_server(self):
        no_dev = hostperm.ClaudeFacts(installs_allowed=True, retired=[], reason=None, allow=["Bash(npm install *)"])
        r = hostperm.compare("claude-desktop", str(self.repo), None, no_dev, self.needs(dev="Bash(pnpm dev)"))
        self.assertEqual(r.state, "bad")
        self.assertIn("开发服务命令 pnpm dev 没放行", r.evidence)
        for words in ("重跑接入", "去会话操作"):
            self.assertIn(words, r.fix)
        ok = hostperm.ClaudeFacts(installs_allowed=True, retired=[], reason=None,
                                  allow=["Bash(npm install *)", "Bash(pnpm dev)"])
        self.assertEqual(hostperm.compare("claude-desktop", str(self.repo), None, ok,
                                          self.needs(dev="Bash(pnpm dev)")).state, "ok")


if __name__ == "__main__":
    unittest.main()


class JoinPreviewTest(unittest.TestCase):
    """host-permission-check: a Codex dev line whose Plan needs network but cannot have it gets a ⚠ at join."""

    def setUp(self):
        import os
        from helpers import TempHomeTestCase  # noqa: F401  (same isolation as the other onboard tests)
        self.tmp = Path(tempfile.mkdtemp(prefix="di-host-join-"))
        self._env = {k: os.environ.get(k) for k in ("DECISION_INBOX_HOME", "DECISION_INBOX_CODEX_CONFIG")}
        os.environ["DECISION_INBOX_HOME"] = str(self.tmp / "home")
        os.environ["DECISION_INBOX_CODEX_CONFIG"] = str(self.tmp / "codex.toml")
        (self.tmp / "codex.toml").write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")
        from decision_inbox import onboard
        (self.tmp / "hub").mkdir()
        onboard.hub("demo", "di-hub", "local_00000000-0000-0000-0000-000000000001", self.tmp / "hub", True,
                    "2026-10-19T12:00:00+08:00")
        self.repo = self.tmp / "app"
        (self.repo / "tasks" / "m").mkdir(parents=True)

    def tearDown(self):
        import os
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def join(self, needs):
        from decision_inbox import onboard
        if needs != "无":
            (self.repo / "package.json").write_text("{}", encoding="utf-8")
        return onboard.join("demo", role="dev", relay_name="app", short_name="应用", host="codex-desktop",
                            lines=["应用"], desktop_session=None, project=self.repo, reviewer=None, nodes=[],
                            confirm=False, now="2026-10-19T12:00:00+08:00", session_cwd=str(self.repo))

    def test_warns_with_both_options(self):
        notes = [w for w in self.join("装 vitest").warnings if "宿主权限" in w]
        self.assertEqual(len(notes), 1)
        for words in ("不能联网", "A 你自己改", "B 不改", "doctor"):
            self.assertIn(words, notes[0])

    def test_quiet_when_matched(self):
        self.assertFalse([w for w in self.join("无").warnings if "宿主权限" in w])
