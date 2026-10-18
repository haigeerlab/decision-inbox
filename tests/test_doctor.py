import json
import os
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import doctor, install, onboard, store

NOW = "2026-10-17T22:00:00+08:00"


class DoctorCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.work = self.home / "work"
        (self.work / "hub").mkdir(parents=True)
        (self.work / "dev").mkdir()
        self.records = self.home / "installed_plugins.json"
        self.codex = self.home / "codex-config.toml"
        self._env = {k: os.environ.get(k) for k in ("DECISION_INBOX_PLUGINS_FILE", "DECISION_INBOX_CODEX_CONFIG")}
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.records)
        os.environ["DECISION_INBOX_CODEX_CONFIG"] = str(self.codex)
        self.write_records({})
        onboard.hub("g", "g-hub", "local_1", self.work / "hub", True, NOW)
        onboard.join("g", "dev", "g-dev", "开发", "codex-desktop", ["web"], None, self.work / "dev",
                     None, (), True, NOW, session_cwd=str(self.work / "dev"))

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def write_records(self, plugins):
        self.records.write_text(json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8")

    def plugin(self, name, version, interface=None):
        root = self.home / "plugins" / name / version
        root.mkdir(parents=True, exist_ok=True)
        if interface is not None:
            (root / "interface.json").write_text(json.dumps(interface), encoding="utf-8")
        return {"scope": "user", "installPath": str(root), "version": version}

    def check(self, name, checks=None):
        checks = checks if checks is not None else doctor.run(["g"], NOW)
        found = [c for c in checks if c.name == name]
        self.assertEqual(len(found), 1, [c.name for c in checks])
        return found[0]


class ConventionTest(DoctorCase):
    def test_current_blocks_are_ok(self):
        self.assertEqual(self.check("约定块：收件枢纽").state, "ok")
        self.assertEqual(self.check("约定块：开发").state, "ok")

    def test_old_block_is_bad_with_fix(self):
        rules = self.work / "dev" / "AGENTS.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("### 开发线", "### 开发线（旧）"), encoding="utf-8")
        c = self.check("约定块：开发")
        self.assertEqual((c.state, c.source), ("bad", "本插件"))
        self.assertIn("不是当前版本", c.evidence)
        self.assertIn("onboard join g", c.fix)

    def test_crew_coordinator_block_is_ok_and_fix_keeps_the_flag(self):
        (self.work / "crew").mkdir()
        onboard.join("g", "dev", "g-crew", "并行", "claude-desktop", ["web"], "local_2", self.work / "crew",
                     None, (), True, NOW, crew_coordinator=True)
        self.assertEqual(self.check("约定块：并行").state, "ok")
        rules = self.work / "crew" / "CLAUDE.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("### 开发线", "### 开发线（旧）"), encoding="utf-8")
        self.assertIn("--crew-coordinator", self.check("约定块：并行").fix)

    def test_local_rules_block_is_checked(self):
        (self.work / "crew").mkdir()
        onboard.join("g", "dev", "g-crew", "并行", "claude-desktop", ["web"], "local_2", self.work / "crew",
                     None, (), True, NOW, local_rules=True)
        self.assertEqual(self.check("约定块：并行").state, "ok")
        rules = self.work / "crew" / "CLAUDE.local.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("### 开发线", "### 开发线（旧）"), encoding="utf-8")
        self.assertIn("--local-rules", self.check("约定块：并行").fix)

    def test_missing_block_is_bad(self):
        (self.work / "dev" / "AGENTS.md").write_text("# 只剩项目规则\n", encoding="utf-8")
        c = self.check("约定块：开发")
        self.assertEqual(c.state, "bad")
        self.assertIn("没有 decision-inbox 约定块", c.evidence)


class ShimTest(DoctorCase):
    def test_points_here(self):
        self.assertEqual(self.check("转发脚本").state, "ok")

    def test_points_elsewhere(self):
        install.write_shim(self.home / "old-plugin")
        c = self.check("转发脚本")
        self.assertEqual(c.state, "bad")
        self.assertIn(str(self.home / "old-plugin"), c.evidence)
        self.assertIn("shim", c.fix)


class PatrolTest(DoctorCase):
    def test_never_registered_is_unknown(self):
        self.assertEqual(self.check("巡视").state, "unknown")

    def test_stale_and_fresh(self):
        onboard.record_task("g", "decision-inbox-patrol-g", "2026-10-17T20:00:00+08:00")
        g = store.open_group("g")
        with g.transaction() as tx:
            tx.write_state("patrol", {"lastRunAt": "2026-10-17T21:00:00+08:00"})
        c = self.check("巡视")
        self.assertEqual((c.state, c.source), ("bad", "Claude 桌面版"))
        self.assertIn("60 分钟没跑", c.evidence)
        self.assertIn("宿主没按时触发（宿主差异 H24）", c.fix)  # patrol-cadence: both causes
        self.assertIn("停在权限确认上，就批完", c.fix)
        with g.transaction() as tx:
            tx.write_state("patrol", {"lastRunAt": "2026-10-17T21:58:00+08:00"})
        self.assertEqual(self.check("巡视").state, "ok")


class HookTrustTest(DoctorCase):
    def test_codex_trust_states(self):
        self.assertEqual(self.check("Codex 钩子信任").state, "unknown")
        self.codex.write_text('[hooks.state."decision-inbox@m:hooks/hooks.json:stop:0:0"]\n'
                              'trusted_hash = "sha256:ab"\nenabled = true\n', encoding="utf-8")
        self.assertEqual(self.check("Codex 钩子信任").state, "ok")
        self.codex.write_text('[hooks.state."decision-inbox@m:hooks/hooks.json:stop:0:0"]\n'
                              'enabled = false\n', encoding="utf-8")
        c = self.check("Codex 钩子信任")
        self.assertEqual((c.state, c.source), ("bad", "Codex"))

    def test_no_codex_session_skips_codex_trust(self):
        onboard.leave("g", "g-dev", self.work / "dev", True, NOW)
        names = [c.name for c in doctor.run(["g"], NOW)]
        self.assertNotIn("Codex 钩子信任", names)


class DependencyTest(DoctorCase):
    def test_three_dependencies(self):
        self.write_records({
            "agent-relay@m": [self.plugin("agent-relay", "0.8.2", {"interface": "2.5"})],
            "spec-guard@m": [self.plugin("spec-guard", "0.67.0", {"interface": "2.0"})],
            "delegate@m": [self.plugin("delegate", "0.5.2")]})
        checks = doctor.run(["g"], NOW)
        relay, sg, dl = (self.check(n, checks) for n in ("依赖：agent-relay", "依赖：spec-guard", "依赖：delegate"))
        self.assertEqual((relay.state, relay.evidence), ("ok", "agent-relay 0.8.2：接口 2.5，兼容"))
        self.assertEqual((sg.state, sg.source), ("bad", "spec-guard"))
        self.assertEqual((dl.state, dl.source), ("unknown", "delegate"))
        self.assertIn("/delegate:doctor", dl.fix)
        self.assertNotIn("没装", dl.evidence)

    def test_optional_not_installed_vs_relay_missing(self):
        checks = doctor.run(["g"], NOW)
        self.assertEqual(self.check("依赖：agent-relay", checks).state, "bad")
        self.assertEqual(self.check("依赖：delegate", checks).state, "ok")
        self.assertIn("可选", self.check("依赖：delegate", checks).evidence)


class OutputTest(DoctorCase):
    def test_json_fields_fixed(self):
        doc = json.loads(doctor.to_json(doctor.run(["g"], NOW)))
        self.assertEqual(doc["schemaVersion"], 1)
        self.assertEqual(set(doc["checks"][0]), {"name", "state", "source", "evidence", "fix"})

    def test_report_lists_only_problems_and_versions(self):
        install.write_shim(self.home / "old-plugin")
        text = doctor.report(doctor.run(["g"], NOW))
        self.assertIn("decision-inbox 异常报告", text)
        self.assertIn("转发脚本", text)
        self.assertIn("decision-inbox ", text)
        self.assertNotIn("约定块：收件枢纽", text)

    def test_render_marks_and_sources(self):
        install.write_shim(self.home / "old-plugin")
        text = doctor.render(doctor.run(["g"], NOW))
        self.assertIn("✘ 转发脚本", text)
        self.assertIn("（来源：本插件）", text)
        self.assertIn("✔ 约定块：收件枢纽", text)


class CliTest(DoctorCase):
    def test_exit_codes_and_modes(self):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["doctor", "--group", "g", "--json"])
        self.assertEqual(code, 3)                 # agent-relay not installed in this temp home
        self.assertEqual(json.loads(buf.getvalue())["schemaVersion"], 1)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["doctor", "--group", "nope"]), 2)
            self.assertEqual(main(["doctor", "--json", "--report"]), 2)


from test_crew import INTERFACE, FakeCrew  # noqa: E402


class ModuleCrewTest(DoctorCase):
    """crew-line-status Task 4."""

    def join_coordinator(self):
        (self.work / "crew").mkdir()
        onboard.join("g", "dev", "g-crew", "并行", "claude-desktop", ["web"], "local_2", self.work / "crew",
                     None, (), True, NOW, crew_coordinator=True)

    def test_optional_without_coordinator(self):
        c = self.check("依赖：module-crew")
        self.assertEqual(c.state, "ok")
        self.assertIn("可选", c.evidence)
        self.assertFalse([x for x in doctor.run(["g"], NOW) if x.name.startswith("module-crew 出口")])

    def test_coordinator_without_module_crew_is_bad(self):
        self.join_coordinator()
        c = self.check("依赖：module-crew")
        self.assertEqual((c.state, c.source), ("bad", "module-crew"))
        self.assertIn("并行开发协调会话", c.fix)
        out = self.check("module-crew 出口：并行")
        self.assertEqual(out.state, "bad")
        self.assertIn("没有安装 module-crew", out.evidence)

    def test_versions_and_contract(self):
        self.join_coordinator()
        FakeCrew(self.home)
        c = self.check("依赖：module-crew")
        self.assertEqual((c.state, c.evidence), ("ok", "module-crew 0.0.1：接口 1.0，兼容，契约 1.7"))
        out = self.check("module-crew 出口：并行")
        self.assertEqual((out.state, out.source, out.evidence), ("ok", "module-crew", "读到 2 个模块会话"))
        for contract, state, words in (("1.8", "ok", "本插件按 1.7"), ("2.0", "bad", "契约 2.0")):
            with self.subTest(contract=contract):
                import shutil
                shutil.rmtree(self.home / "module-crew")
                FakeCrew(self.home, interface=dict(INTERFACE, contract=contract))
                c = self.check("依赖：module-crew")
                self.assertEqual(c.state, state)
                self.assertIn(words, c.evidence)

    def test_interface_major_and_unreadable_output(self):
        self.join_coordinator()
        FakeCrew(self.home, interface=dict(INTERFACE, interface="2.0"), out="", code=2, err="状态库坏了")
        self.assertEqual(self.check("依赖：module-crew").state, "bad")
        import shutil
        shutil.rmtree(self.home / "module-crew")
        FakeCrew(self.home, out="", code=2, err="状态库坏了")
        out = self.check("module-crew 出口：并行")
        self.assertEqual((out.state, out.evidence), ("bad", "状态库坏了"))
        self.assertIn("模块状态未知", out.fix)
