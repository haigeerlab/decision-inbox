import json
import os
import re
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import doctor, install, onboard, protocol, store

NOW = "2026-10-17T22:00:00+08:00"


class DoctorCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.work = self.home / "work"
        (self.work / "hub").mkdir(parents=True)
        (self.work / "dev").mkdir()
        self.records = self.home / "installed_plugins.json"
        self.codex = self.home / "codex-config.toml"
        self._env = {k: os.environ.get(k) for k in ("DECISION_INBOX_PLUGINS_FILE", "DECISION_INBOX_CODEX_CONFIG",
                                                     "DECISION_INBOX_TRANSCRIPTS")}
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.records)
        os.environ["DECISION_INBOX_CODEX_CONFIG"] = str(self.codex)
        self.transcripts = self.home / "projects"
        os.environ["DECISION_INBOX_TRANSCRIPTS"] = str(self.transcripts)
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
        self.assertEqual(self.check("协作规则段：决策收件箱").state, "ok")
        self.assertEqual(self.check("协作规则段：开发").state, "ok")

    def test_old_block_is_bad_with_fix(self):
        rules = self.work / "dev" / "AGENTS.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("### 开发线", "### 开发线（旧）"), encoding="utf-8")
        c = self.check("协作规则段：开发")
        self.assertEqual((c.state, c.source), ("bad", "本插件"))
        self.assertIn("不是当前版本", c.evidence)
        self.assertIn("onboard join g", c.fix)

    def test_crew_coordinator_block_is_ok_and_fix_keeps_the_flag(self):
        (self.work / "crew").mkdir()
        onboard.join("g", "dev", "g-crew", "并行", "claude-desktop", ["web"], "local_2", self.work / "crew",
                     None, (), True, NOW, crew_coordinator=True)
        self.assertEqual(self.check("协作规则段：并行").state, "ok")
        rules = self.work / "crew" / "CLAUDE.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("### 开发线", "### 开发线（旧）"), encoding="utf-8")
        self.assertIn("--crew-coordinator", self.check("协作规则段：并行").fix)

    def test_local_rules_block_is_checked(self):
        (self.work / "crew").mkdir()
        onboard.join("g", "dev", "g-crew", "并行", "claude-desktop", ["web"], "local_2", self.work / "crew",
                     None, (), True, NOW, local_rules=True)
        self.assertEqual(self.check("协作规则段：并行").state, "ok")
        rules = self.work / "crew" / "CLAUDE.local.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("### 开发线", "### 开发线（旧）"), encoding="utf-8")
        self.assertIn("--local-rules", self.check("协作规则段：并行").fix)

    def test_missing_block_is_bad(self):
        (self.work / "dev" / "AGENTS.md").write_text("# 只剩项目规则\n", encoding="utf-8")
        c = self.check("协作规则段：开发")
        self.assertEqual(c.state, "bad")
        self.assertIn("没有 decision-inbox 协作规则段", c.evidence)


class StrayBlockTest(DoctorCase):
    """rules-dir-guard 要做的 3: a block in a member directory's parent is loaded by that member too."""

    NAME = "上级目录的协作规则段"

    def stray(self, path):
        return self.check(f"{self.NAME}：{path}")

    def test_none_is_ok(self):
        c = self.check(self.NAME)
        self.assertEqual(c.state, "ok")
        self.assertFalse(any(x.name.startswith(self.NAME + "：") for x in doctor.run(["g"], NOW)))

    def test_unrecorded_block_in_group_directory_is_bad_once(self):
        stray = self.work / "CLAUDE.md"
        stray.write_text("# 组目录\n\n" + onboard.block("hub", "g", "g-hub"), encoding="utf-8")
        c = self.stray(stray)
        self.assertEqual((c.state, c.source), ("bad", "本插件"))
        for needle in (str(stray), "决策收件箱", "开发", "一起加载"):
            self.assertIn(needle, c.evidence)
        self.assertIn("手动删掉", c.fix)
        stray.write_text("# 组目录\n", encoding="utf-8")
        self.assertEqual(self.check(self.NAME).state, "ok")

    def test_recorded_block_names_its_owner(self):
        """The 2026-10-20 field case: the roster points at the group directory's CLAUDE.md."""
        stray = self.work / "CLAUDE.md"
        stray.write_text(onboard.block("hub", "g", "g-hub"), encoding="utf-8")
        g = store.open_group("g")
        with g.transaction() as tx:
            doc = tx.read_state(onboard.DOMAIN)
            doc["files"]["g-hub"] = str(stray)
            tx.write_state(onboard.DOMAIN, doc)
        c = self.stray(stray)
        self.assertEqual(c.state, "bad")
        self.assertIn("开发", c.evidence)
        self.assertIn("让 决策收件箱 到不包含其他成员目录的目录重跑接入，加 --drop-old", c.fix)

    def test_same_directory_counts_and_left_member_does_not(self):
        stray = self.work / "dev" / "CLAUDE.md"
        stray.write_text(onboard.block("hub", "g", "g-hub"), encoding="utf-8")
        self.assertEqual(self.stray(stray).state, "bad")
        onboard.leave("g", "g-dev", None, True, NOW)
        self.assertEqual(self.check(self.NAME).state, "ok")


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


class TornDownTest(DoctorCase):
    """doctor-skip-teardown: a group whose decision inbox has left is not checked for patrol."""

    def stale_patrol_and_leave(self, left):
        onboard.record_task("g", "decision-inbox-patrol-g", "2026-10-15T20:00:00+08:00")
        g = store.open_group("g")
        with g.transaction() as tx:
            tx.write_state("patrol", {"lastRunAt": "2026-10-15T21:00:00+08:00"})
            tx.write_state(onboard.DOMAIN, {**tx.read_state(onboard.DOMAIN), "left": left})

    def test_torn_down_group_is_ok_and_not_counted(self):
        self.stale_patrol_and_leave({"g-hub": "2026-10-17T21:30:00+08:00", "g-dev": "2026-10-17T21:29:00+08:00"})
        c = self.check("巡视")
        self.assertEqual(c.state, "ok")
        for words in ("g 的决策收件箱已卸载", "10-17 21:30", "状态目录保留", "不再检查巡视"):
            self.assertIn(words, c.evidence)
        self.assertIn("异常 0", doctor.render([c]))

    def test_only_a_line_left_is_still_checked(self):
        self.stale_patrol_and_leave({"g-dev": NOW})
        self.assertEqual(self.check("巡视").state, "bad")

    def test_hub_set_up_again_is_checked_again(self):
        self.stale_patrol_and_leave({"g-hub": "2026-10-17T21:30:00+08:00"})
        onboard.hub("g", "g-hub", "local_1", self.work / "hub", True, NOW)
        self.assertEqual(self.check("巡视").state, "bad")

    def test_no_hub_in_roster_is_checked_as_before(self):
        solo, _ = store.init_group("solo")
        with solo.transaction() as tx:
            tx.add_session({"relayName": "s-dev", "shortName": "独立", "role": "dev", "line": ["web"],
                            "host": "codex-desktop", "repo": str(self.work / "dev")})
        onboard.record_task("solo", "decision-inbox-patrol-solo", "2026-10-15T20:00:00+08:00")
        with store.open_group("solo").transaction() as tx:
            tx.write_state("patrol", {"lastRunAt": "2026-10-15T21:00:00+08:00"})
            tx.write_state(onboard.DOMAIN, {**tx.read_state(onboard.DOMAIN), "left": {"s-dev": NOW}})
        self.assertEqual(self.check("巡视", doctor.run(["solo"], NOW)).state, "bad")


class HostPermissionTest(DoctorCase):
    """host-permission-check, permission-closeout: each dev line's host against what its repository needs to install."""

    def setUp(self):
        super().setUp()
        self.codex.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")

    def manifest(self, name="package.json", text='{"dependencies": {}}'):
        (self.work / "dev").mkdir(parents=True, exist_ok=True)
        (self.work / "dev" / name).write_text(text, encoding="utf-8")

    def test_bad_lists_both_options_and_writes_nothing(self):
        self.manifest()
        before = (self.codex.read_bytes(), sorted(p.name for p in (self.work / "dev").rglob("*")))
        c = self.check("宿主权限：开发")
        self.assertEqual((c.state, c.source), ("bad", "Codex"))
        self.assertIn("不能联网", c.evidence)
        for words in ("A 你自己改", "先在 Codex 里信任这个项目", "network_access = true", "没实测", "B 不改"):
            self.assertIn(words, c.fix)
        self.assertEqual((self.codex.read_bytes(), sorted(p.name for p in (self.work / "dev").rglob("*"))), before)

    def test_ok_without_a_manifest_and_plan_does_not_matter(self):
        (self.work / "dev" / "tasks" / "m").mkdir(parents=True, exist_ok=True)
        (self.work / "dev" / "tasks" / "m" / "plan.md").write_text("需要的外部条件：装 vitest\n", encoding="utf-8")
        c = self.check("宿主权限：开发")
        self.assertEqual(c.state, "ok")
        self.assertIn("没有依赖清单", c.evidence)
        self.assertIn("异常 0", doctor.render([c]))

    def test_unknown_when_config_unreadable(self):
        self.manifest("requirements.txt", "requests\n")
        self.codex.unlink()
        c = self.check("宿主权限：开发")
        self.assertEqual(c.state, "unknown")
        self.assertIn("读不到", c.evidence)

    def test_only_dev_lines(self):
        self.assertFalse([c for c in doctor.run(["g"], NOW) if c.name.startswith("宿主权限：") and "开发" not in c.name])


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
        self.assertNotIn("协作规则段：决策收件箱", text)

    def test_render_marks_and_sources(self):
        install.write_shim(self.home / "old-plugin")
        text = doctor.render(doctor.run(["g"], NOW))
        self.assertIn("✘ 转发脚本", text)
        self.assertIn("（来源：本插件）", text)
        self.assertIn("✔ 协作规则段：决策收件箱", text)


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
        self.assertIn("模块协调", c.fix)
        out = self.check("module-crew 出口：并行")
        self.assertEqual(out.state, "bad")
        self.assertIn("没有安装 module-crew", out.evidence)

    def test_versions_and_contract(self):
        self.join_coordinator()
        FakeCrew(self.home)
        c = self.check("依赖：module-crew")
        self.assertEqual((c.state, c.evidence),
                         ("ok", f"module-crew 0.0.1：接口 1.0，兼容，契约 {protocol.CONTRACT_VERSION}"))
        out = self.check("module-crew 出口：并行")
        self.assertEqual((out.state, out.source, out.evidence), ("ok", "module-crew", "读到 2 个模块会话"))
        # review-nearby: pinned to 2.x now, so a 1.x module-crew (0.2.x speaks 1.9) is a mismatch
        for contract, state, words in (("2.9", "ok", f"本插件按 {protocol.CONTRACT_VERSION}"),
                                       ("1.9", "bad", "契约 1.9")):
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


class EnrolledEntryTest(DoctorCase):
    """rehearsal-fixes Task 2: an enrolled entry has no block by design."""

    def test_enrolled_entry_is_ok(self):
        onboard.enroll("g", "g-legacy", "旧格式", "claude-desktop", ["web"], None, True, NOW)
        c = self.check("协作规则段：旧格式")
        self.assertEqual((c.state, c.evidence), ("ok", "只登记，不写协作规则段（迁移期旧格式会话）"))
        self.assertEqual(self.check("协作规则段：开发").state, "ok")


class HostVersionsTest(DoctorCase):
    """rehearsal-fixes Task 4: Claude and Codex should run the same decision-inbox."""

    NAME = "Claude、Codex 两边的版本"

    def claude(self, version):
        self.write_records({"decision-inbox@m": [self.plugin("decision-inbox", version)]})
        root = self.home / "plugins" / "decision-inbox" / version / ".claude-plugin"
        root.mkdir(parents=True, exist_ok=True)
        (root / "plugin.json").write_text(json.dumps({"version": version}), encoding="utf-8")

    def set_codex(self, *versions, enabled=True, market="mk"):
        self.codex.write_text(f'[plugins."decision-inbox@{market}"]\nenabled = {str(enabled).lower()}\n',
                              encoding="utf-8")
        for v in versions:
            d = self.home / "plugins" / "cache" / market / "decision-inbox" / v / ".codex-plugin"
            d.mkdir(parents=True, exist_ok=True)
            (d / "plugin.json").write_text(json.dumps({"version": v}), encoding="utf-8")

    def test_same_version_is_ok(self):
        self.claude("0.0.19")
        self.set_codex("0.0.19")
        c = self.check(self.NAME)
        self.assertEqual(c.state, "ok")
        self.assertIn("Claude 0.0.19", c.evidence)
        self.assertIn("Codex 0.0.19", c.evidence)

    def test_mismatch_is_bad_with_commands(self):
        self.claude("0.0.19")
        self.set_codex("0.0.15")
        c = self.check(self.NAME)
        self.assertEqual((c.state, c.source), ("bad", "Claude Code／Codex 安装"))
        self.assertIn("codex plugin remove decision-inbox@mk", c.fix)
        self.assertIn("codex plugin add decision-inbox@mk", c.fix)

    def test_two_cached_versions_is_bad(self):
        self.claude("0.0.19")
        self.set_codex("0.0.15", "0.0.19")
        c = self.check(self.NAME)
        self.assertEqual(c.state, "bad")
        self.assertIn("0.0.15、0.0.19", c.evidence)

    def test_one_side_only_is_ok(self):
        self.claude("0.0.19")
        self.set_codex("0.0.19", enabled=False)
        c = self.check(self.NAME)
        self.assertEqual(c.state, "ok")
        self.assertIn("Codex 没装", c.evidence)
        self.codex.unlink()
        self.assertIn("Codex 没装", self.check(self.NAME).evidence)
        self.write_records({})
        self.set_codex("0.0.19")
        c = self.check(self.NAME)
        self.assertEqual(c.state, "ok")
        self.assertIn("Claude 没装", c.evidence)

    def test_neither_side_is_bad(self):
        """review-nearby Task 2 (O-doctor-none): nothing installed on either side is not ok."""
        self.write_records({})
        self.set_codex("0.0.19", enabled=False)
        c = self.check(self.NAME)
        self.assertEqual(c.state, "bad")
        self.assertIn("两边都没装", c.evidence)
        self.assertIn("codex plugin add", c.fix)
        self.assertIn("固定副本安装", c.fix)

    def test_unreadable_codex_cache_is_unknown(self):
        self.claude("0.0.19")
        self.set_codex()
        c = self.check(self.NAME)
        self.assertEqual(c.state, "unknown")
        self.assertIn(str(self.home / "plugins" / "cache" / "mk" / "decision-inbox"), c.evidence)


class HubTranscriptTest(DoctorCase):
    """decision-cards Task 6: whether the hub's stop check can read this host's session records.

    hub-stop-scope: only the hub's own records count, found under its rules file's folder.
    """

    NAME = "收件箱停止检查"
    VIEWED = [{"type": "user", "message": {"content": "看"}},
              {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t", "name": "Bash",
                                                             "input": {"command": "decision-inbox view g"}}]}},
              {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t",
                                                        "content": "等你决定 0 项"}]}}]

    @staticmethod
    def folder_name(path):
        return re.sub(r"[^A-Za-z0-9]", "-", str(path))

    def hub_folder(self, real=False):
        rules = store.read_state(store.open_group("g"), "onboarding")["files"]["g-hub"]
        folder = os.path.dirname(rules)
        return self.transcripts / self.folder_name(os.path.realpath(folder) if real else folder)

    def record(self, rows, name="a.jsonl", folder=None):
        folder = folder or self.hub_folder()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    def test_no_record_yet_is_unknown(self):
        self.assertEqual(self.check(self.NAME).state, "unknown")

    def test_readable_record_is_ok(self):
        self.record(self.VIEWED)
        c = self.check(self.NAME)
        self.assertEqual(c.state, "ok")
        self.assertIn("g 的收件箱", c.evidence)

    def test_unreadable_record_is_bad(self):
        folder = self.hub_folder()
        folder.mkdir(parents=True)
        (folder / "a.jsonl").write_text('{"x": "decision-inbox view g"\n', encoding="utf-8")
        c = self.check(self.NAME)
        self.assertEqual(c.state, "bad")
        self.assertIn("读不懂", c.evidence)

    def test_other_sessions_records_do_not_count(self):
        other = self.transcripts / "-elsewhere"
        other.mkdir(parents=True)
        (other / "b.jsonl").write_text('{"x": "decision-inbox view g"\n', encoding="utf-8")
        self.assertEqual(self.check(self.NAME).state, "unknown")
        self.record(self.VIEWED)
        self.assertEqual(self.check(self.NAME).state, "ok")

    def test_realpath_folder_is_found(self):
        self.record(self.VIEWED, folder=self.hub_folder(real=True))
        self.assertEqual(self.check(self.NAME).state, "ok")

    def test_hub_without_rules_file_is_unknown(self):
        g = store.open_group("g")
        with g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc["files"].pop("g-hub")
            tx.write_state("onboarding", doc)
        c = self.check(self.NAME)
        self.assertEqual(c.state, "unknown")
        self.assertIn("没有记下规则文件", c.evidence)
