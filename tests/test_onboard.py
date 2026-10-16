import re
import unittest

from helpers import TempHomeTestCase

from decision_inbox import hub, onboard, patrol, protocol, reviews, store

DEV = "<!-- BEGIN decision-inbox dev -->\n## dev rules\n<!-- END decision-inbox dev -->\n"
DEV2 = "<!-- BEGIN decision-inbox dev -->\n## dev rules v2\nmore\n<!-- END decision-inbox dev -->\n"
OWNER = "<!-- BEGIN decision-inbox owner -->\n## owner rules\n<!-- END decision-inbox owner -->\n"


class PlaceTest(unittest.TestCase):
    def test_empty_file(self):
        self.assertEqual(onboard.place("", "dev", DEV), DEV)

    def test_appended_after_existing_content(self):
        text = "# 项目规则\n\n- 用中文\n"
        self.assertEqual(onboard.place(text, "dev", DEV), text + "\n" + DEV)

    def test_no_trailing_newline_gets_one(self):
        self.assertEqual(onboard.place("# x", "dev", DEV), "# x\n\n" + DEV)

    def test_same_role_replaced_in_place(self):
        for before, after in (("", ""), ("# 头\n\n", ""), ("", "\n## 尾\n"), ("# 头\n\n", "\n## 尾\n")):
            text = before + DEV + after
            self.assertEqual(onboard.place(text, "dev", DEV2), before + DEV2 + after)

    def test_other_role_or_broken_markers_conflict(self):
        for text in ("# x\n\n" + OWNER,
                     "<!-- BEGIN decision-inbox dev -->\n半截\n",
                     "孤立\n<!-- END decision-inbox dev -->\n",
                     DEV + "\n" + DEV,
                     "<!-- BEGIN decision-inbox dev -->\n<!-- END decision-inbox owner -->\n"):
            with self.assertRaises(onboard.BlockConflict):
                onboard.place(text, "dev", DEV2)

    def test_marker_must_be_whole_line(self):
        text = "说明：标记写作 <!-- BEGIN decision-inbox dev --> 这样\n"
        self.assertEqual(onboard.place(text, "dev", DEV), text + "\n" + DEV)


class StripTest(unittest.TestCase):
    def test_round_trip_keeps_everything_else(self):
        for text in ("", "# 项目规则\n\n- 用中文\n", "a\n\n\nb\n"):
            self.assertEqual(onboard.strip(onboard.place(text, "dev", DEV)), (text, True))

    def test_round_trip_without_trailing_newline_only_adds_it(self):
        self.assertEqual(onboard.strip(onboard.place("# x", "dev", DEV)), ("# x\n", True))

    def test_block_in_the_middle(self):
        text = "# 头\n\n" + OWNER + "\n## 尾\n"
        self.assertEqual(onboard.strip(text), ("# 头\n\n## 尾\n", True))

    def test_block_at_start(self):
        self.assertEqual(onboard.strip(DEV + "\n## 尾\n"), ("## 尾\n", True))

    def test_no_block_unchanged(self):
        self.assertEqual(onboard.strip("# 头\n"), ("# 头\n", False))

    def test_broken_markers_conflict(self):
        with self.assertRaises(onboard.BlockConflict):
            onboard.strip("<!-- BEGIN decision-inbox dev -->\n半截\n")


COMMON = ("协作组「demo」", "di-hub", "bridge_send", "replyTo", "回复：#", "expectsReply",
          "【等待用户】", "【等待其他会话】", "【已恢复】", "【撤回】", "【取代 #", "【与 #", "结束：",
          "选了会怎样", "你该回", "只认收件枢纽", "回显", "不是用户批准", "被挡住", "悄悄停下", "停止钩子", "原会话")
ONLY = {
    "dev": ("只抛本线", "架构审查：", "交付时", "适用于你的范围"),
    "owner": ("【讨论】", "【审查结论】", "【进度】", "【提案已抛】", "审查编号", "模块：", "送审方",
              "就这么定了", "【进度预警】", "各线范围", "适用会话", "适用于你的范围"),
    "coordinator": ("各线范围", "适用会话", "核对不是审查", "不批任何东西"),
}
KINDS = {
    "dev": {"wait-user", "wait-session", "resumed", "withdraw"},
    "owner": {"wait-user", "wait-session", "resumed", "withdraw", "review-conclusion"},
    "coordinator": {"wait-user", "wait-session", "resumed", "withdraw"},
}
_FENCE_RE = re.compile(r"```text\n(.*?)```", re.S)


class BlockTextTest(unittest.TestCase):
    def block(self, role):
        return onboard.block(role, group="demo", hub_relay="di-hub")

    def test_markers(self):
        for role in ("dev", "owner", "coordinator"):
            lines = self.block(role).rstrip("\n").split("\n")
            self.assertEqual(lines[0], f"<!-- BEGIN decision-inbox {role} -->")
            self.assertEqual(lines[-1], f"<!-- END decision-inbox {role} -->")
            self.assertEqual(onboard.place("", role, self.block(role)), self.block(role))

    def test_rules_per_role(self):
        for role in ("dev", "owner", "coordinator"):
            text = self.block(role)
            for needle in COMMON + ONLY[role]:
                self.assertIn(needle, text, f"{role} 缺「{needle}」")

    def test_rules_not_for_this_role(self):
        self.assertNotIn("各线范围", self.block("dev"))
        self.assertNotIn("【讨论】", self.block("dev"))
        self.assertNotIn("【讨论】", self.block("coordinator"))
        self.assertNotIn("【审查结论】", self.block("coordinator"))
        self.assertNotIn("核对不是审查", self.block("owner"))

    def test_templates_parse_cleanly(self):
        for role, kinds in KINDS.items():
            seen = set()
            for template in _FENCE_RE.findall(self.block(role)):
                msg = protocol.parse(template)
                self.assertEqual(msg.problems, (), f"{role} 的模板解析有问题：{template}")
                seen.add(msg.kind)
                if role in ("owner", "coordinator") and "适用会话" in template:
                    self.assertTrue(msg.lines_in_scope)
            self.assertEqual(seen, kinds, role)

    def test_hub_block_is_hub_loop_convention(self):
        self.assertEqual(onboard.block("hub", group="demo", hub_relay="di-hub"), hub.convention("demo"))


NOW = "2026-10-17T01:00:00Z"
HUB_DESKTOP = "local_00000000-0000-0000-0000-00000000hub0"


class OnboardCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.project = self.home / "projects"
        self.project.mkdir()

    def dir(self, name):
        path = self.project / name
        path.mkdir(exist_ok=True)
        return path

    def files(self):
        return {str(f.relative_to(self.home)): f.read_bytes() for f in sorted(self.home.rglob("*")) if f.is_file()}

    def hub(self, confirm=True, **kw):
        args = dict(relay_name="di-hub", desktop_session=HUB_DESKTOP, project=self.dir("hub"), confirm=confirm, now=NOW)
        args.update(kw)
        return onboard.hub("demo", **args)


class HubTest(OnboardCase):
    def test_preview_changes_nothing(self):
        before = self.files()
        out = self.hub(confirm=False)
        self.assertEqual(self.files(), before)
        self.assertFalse((self.home / "demo").exists())
        self.assertEqual(out.file, self.project / "hub" / "CLAUDE.md")
        self.assertTrue(out.changed)
        self.assertIn("<!-- BEGIN decision-inbox hub -->", out.after)

    def test_confirm(self):
        (self.dir("hub") / "CLAUDE.md").write_text("# 我的规则\n", encoding="utf-8")
        out = self.hub()
        g = store.open_group("demo")
        entry = store.find_session(g, relay_name="di-hub")
        self.assertEqual((entry["role"], entry["host"], entry["desktopSession"]), ("hub", "claude-desktop", HUB_DESKTOP))
        text = (self.project / "hub" / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# 我的规则\n\n<!-- BEGIN decision-inbox hub -->"))
        self.assertEqual(text, onboard.place("# 我的规则\n", "hub", hub.convention("demo")))
        self.assertTrue((g.path / "io").is_dir())
        self.assertEqual(out.patrol_prompt, patrol.prompt("demo"))
        steps = "\n".join(out.steps)
        for needle in ("create_scheduled_task", "decision-inbox-patrol-demo", "*/5 * * * *", "onboard task demo",
                       "立即运行", "bridge_register", "wake: \"auto\"", "di-hub", "停止钩子", "Claude Code", "Codex",
                       "onboard join demo"):
            self.assertIn(needle, steps)
        state = store.read_state(g, "onboarding")
        self.assertEqual(state["files"]["di-hub"], str(self.project / "hub" / "CLAUDE.md"))

    def test_rerun_replaces_block_and_entry(self):
        self.hub()
        self.hub(desktop_session="local_00000000-0000-0000-0000-00000000hub9")
        g = store.open_group("demo")
        self.assertEqual(store.find_session(g, relay_name="di-hub")["desktopSession"],
                         "local_00000000-0000-0000-0000-00000000hub9")
        self.assertEqual((self.project / "hub" / "CLAUDE.md").read_text(encoding="utf-8").count("BEGIN decision-inbox"), 1)

    def test_second_hub_or_bad_session_rejected_without_writes(self):
        self.hub()
        before = self.files()
        with self.assertRaises(store.InvalidSession):
            self.hub(relay_name="di-hub-2", project=self.dir("hub2"))
        with self.assertRaises(store.InvalidSession):
            onboard.hub("other", relay_name="x", desktop_session="nope", project=self.dir("x"), confirm=True, now=NOW)
        self.assertEqual(self.files(), before)
        self.assertFalse((self.home / "other").exists())

    def test_conflicting_block_rejected(self):
        (self.dir("hub") / "CLAUDE.md").write_text(OWNER, encoding="utf-8")
        with self.assertRaises(onboard.BlockConflict):
            self.hub()
        self.assertFalse((self.home / "demo").exists())


class JoinTest(OnboardCase):
    def setUp(self):
        super().setUp()
        self.hub()

    def join(self, role="dev", relay_name="fe-codex", short_name="前端", host="codex-desktop", lines=("前端",),
             desktop_session=None, project="fe", reviewer=None, nodes=(), confirm=True):
        return onboard.join("demo", role=role, relay_name=relay_name, short_name=short_name, host=host,
                            lines=list(lines), desktop_session=desktop_session, project=self.dir(project),
                            reviewer=reviewer, nodes=list(nodes), confirm=confirm, now=NOW)

    def owner(self):
        return self.join(role="owner", relay_name="fe-owner", short_name="前端负责人", host="claude-desktop",
                         desktop_session="local_00000000-0000-0000-0000-0000000own1", project="owner")

    def test_preview_changes_nothing(self):
        before = self.files()
        out = self.join(confirm=False)
        self.assertEqual(self.files(), before)
        self.assertEqual(out.file, self.project / "fe" / "AGENTS.md")
        self.assertIn("<!-- BEGIN decision-inbox dev -->", out.after)

    def test_dev_on_codex(self):
        self.join()
        g = store.open_group("demo")
        entry = store.find_session(g, relay_name="fe-codex")
        self.assertEqual((entry["role"], entry["line"], entry["repo"]), ("dev", ["前端"], str(self.project / "fe")))
        self.assertNotIn("desktopSession", entry)
        text = (self.project / "fe" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(text, onboard.block("dev", "demo", "di-hub"))
        self.assertFalse((self.project / "fe" / "CLAUDE.md").exists())

    def test_owner_on_claude(self):
        out = self.owner()
        entry = store.find_session(store.open_group("demo"), relay_name="fe-owner")
        self.assertEqual(entry["desktopSession"], "local_00000000-0000-0000-0000-0000000own1")
        self.assertNotIn("repo", entry)
        self.assertEqual(out.file, self.project / "owner" / "CLAUDE.md")
        self.assertIn("【讨论】", out.after)

    def test_rejoin_replaces_entry(self):
        self.join()
        self.join(short_name="前端2")
        g = store.open_group("demo")
        self.assertEqual(store.find_session(g, relay_name="fe-codex")["shortName"], "前端2")
        self.assertEqual(len(store.roster(g)), 2)

    def test_reviewer_registered(self):
        self.owner()
        self.join(reviewer="fe-owner", nodes=("spec", "plan", "final"))
        reg = reviews.registration_at(store.open_group("demo"), "fe-codex", "2026-10-17T02:00:00Z")
        self.assertEqual((reg.reviewer, reg.nodes), ("fe-owner", ("spec", "plan", "final")))
        doc = store.read_state(store.open_group("demo"), "reviews")
        self.assertIn("接入时用户指定", str(doc))

    def test_bad_reviewer_changes_nothing(self):
        before = self.files()
        for reviewer, nodes in (("fe-owner", ("spec",)), ("di-hub", ("spec",))):
            with self.assertRaises(onboard.JoinError):
                self.join(reviewer=reviewer, nodes=nodes)
        self.owner()
        before = self.files()
        for nodes in ((), ("spec", "deploy")):
            with self.assertRaises(onboard.JoinError):
                self.join(reviewer="fe-owner", nodes=nodes)
        self.assertEqual(self.files(), before)

    def test_owner_cannot_take_a_reviewer(self):
        self.owner()
        before = self.files()
        with self.assertRaises(onboard.JoinError):
            self.join(role="owner", relay_name="o2", short_name="负责人2", host="claude-desktop", project="o2",
                      reviewer="fe-owner", nodes=("spec",))
        self.assertEqual(self.files(), before)

    def test_roster_rules_change_nothing(self):
        before = self.files()
        for kw in (dict(lines=()), dict(short_name="收件枢纽"), dict(role="hub", lines=())):
            with self.assertRaises((store.InvalidSession, onboard.JoinError)):
                self.join(**kw)
        self.assertEqual(self.files(), before)

    def test_group_must_have_hub(self):
        with self.assertRaises(store.GroupNotFound):
            onboard.join("nope", role="dev", relay_name="x", short_name="x", host="codex-desktop", lines=["x"],
                         desktop_session=None, project=self.dir("x"), reviewer=None, nodes=[], confirm=True, now=NOW)
        store.init_group("empty")
        with self.assertRaises(onboard.JoinError):
            onboard.join("empty", role="dev", relay_name="x", short_name="x", host="codex-desktop", lines=["x"],
                         desktop_session=None, project=self.dir("x"), reviewer=None, nodes=[], confirm=True, now=NOW)

    def test_steps(self):
        codex = "\n".join(self.join().steps)
        for needle in ("bridge_register", "fe-codex", "wake: \"auto\"", "停止钩子", "Claude Code", "Codex"):
            self.assertIn(needle, codex)
        self.assertNotIn("get_session", codex)
        claude = "\n".join(self.join(role="owner", relay_name="o2", short_name="负责人2", host="claude-desktop",
                                      project="o2").steps)
        self.assertIn("get_session", claude)


if __name__ == "__main__":
    unittest.main()
