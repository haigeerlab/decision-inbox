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
        self.assertEqual(claude["version"], "0.0.22")
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


COMMANDS = ("lines", "flow", "item", "map", "hub-setup", "join", "leave", "teardown", "glossary")
QUERIES = ("lines", "flow", "item", "map")
CHANGES = ("hub-setup", "join", "leave", "teardown")
SUBCOMMANDS = {"store", "query", "map", "hook", "patrol", "inbox", "view", "onboard", "shim", "whoami", "doctor", "notify", "glossary"}


def frontmatter(text):
    head, _, body = text.partition("\n---\n")
    lines = head.split("\n")
    assert lines[0] == "---", "missing frontmatter"
    return dict(line.split(": ", 1) for line in lines[1:] if ": " in line), body


class CommandFilesTest(unittest.TestCase):
    def read(self, rel):
        return (REPO / rel).read_text(encoding="utf-8")

    def test_all_commands_exist_with_description(self):
        self.assertEqual(sorted(p.stem for p in (REPO / "commands").glob("*.md")), sorted(COMMANDS))
        for name in COMMANDS:
            meta, body = frontmatter(self.read(f"commands/{name}.md"))
            self.assertTrue(meta.get("description"), name)
            # Claude Code substitutes only the literal ${CLAUDE_PLUGIN_ROOT} in command text (Task 6 实测).
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox"', body, name)
            self.assertNotIn("CLAUDE_PLUGIN_ROOT:-", body, name)

    def test_queries_show_output_as_is(self):
        for name in QUERIES:
            body = self.read(f"commands/{name}.md")
            self.assertIn("原样", body, name)
            self.assertIn("whoami", body, name)

    def test_changes_preview_then_confirm(self):
        for name in CHANGES:
            body = self.read(f"commands/{name}.md")
            for needle in ("预览", "--confirm", "用户确认"):
                self.assertIn(needle, body, f"{name} 缺「{needle}」")

    def test_tool_steps(self):
        self.assertIn("bridge_agents", self.read("commands/lines.md"))
        self.assertIn("bridge_wake_status", self.read("commands/flow.md"))
        self.assertIn("item-ids", self.read("commands/item.md"))
        self.assertIn("bridge_wake_status", self.read("commands/item.md"))
        setup = self.read("commands/hub-setup.md")
        # stall-and-patrol R18: a looping patrol session replaces the scheduled task
        for needle in ("get_session", "start_session", "/loop 5m", "onboard patrol-session", "delete_scheduled_task",
                       "bridge_register", "巡视还没跑完过"):  # e2e-round1-fixes F4: the first run is checked
            self.assertIn(needle, setup)
        self.assertIn("get_session", self.read("commands/join.md"))
        self.assertIn("--checkpoint-authority", self.read("commands/join.md"))
        self.assertIn("--crew-coordinator", self.read("commands/join.md"))
        self.assertIn("--local-rules", self.read("commands/join.md"))
        self.assertIn("--start-number", self.read("commands/hub-setup.md"))
        self.assertIn("delete_scheduled_task", self.read("commands/teardown.md"))
        glossary = self.read("commands/glossary.md")  # glossary-rename: the help page shows the copy word for word
        self.assertIn("bin/decision-inbox\" glossary", glossary)
        self.assertIn("逐字", glossary)

    def test_codex_skill(self):
        meta, body = frontmatter(self.read("skills/decision-inbox-join/SKILL.md"))
        self.assertEqual(meta.get("name"), "decision-inbox-join")
        self.assertTrue(meta.get("description"))
        for needle in ("whoami", "onboard join", "onboard leave", "codex-desktop", "预览", "--confirm",
                       "bridge_register", "钩子",
                       # relay-checkpoint-authority R1, R2: ask first, show the warnings, open the repo
                       "--checkpoint-authority", "默认不开", "⚠", "仓库"):
            self.assertIn(needle, body)

    def test_only_real_subcommands(self):
        import re
        files = [*(REPO / "commands").glob("*.md"), REPO / "skills/decision-inbox-join/SKILL.md"]
        for path in files:
            for sub in re.findall(r"decision-inbox\"? ([a-z]+)", path.read_text(encoding="utf-8")):
                self.assertIn(sub, SUBCOMMANDS, f"{path.name} 用了不存在的子命令 {sub}")


class ReadmeTest(unittest.TestCase):
    def test_sections_and_commands(self):
        import re
        text = (REPO / "README.md").read_text(encoding="utf-8")
        for needle in ("## 安装", "/plugin marketplace add", "codex plugin marketplace add", "## 接入",
                       "决策收件箱", "审查者", "开发线", "/decision-inbox:glossary", "W 编号", "/decision-inbox:hub-setup", "/decision-inbox:join",
                       "## 日常", "/decision-inbox:lines", "/decision-inbox:flow", "/decision-inbox:item",
                       "/decision-inbox:map", "## 升级", "## 卸载", "/decision-inbox:leave",
                       "/decision-inbox:teardown", "~/.decision-inbox", "保留", "## 排查", "停止钩子", "巡视",
                       "【答复告知】",
                       # e2e-round1-fixes F7, F3, F4
                       "先删掉手贴的旧决策收件箱规则", "亲手输入", "靠决策收件箱遵守约定", "巡视还没跑完过", "被自动模式拦下",
                       # relay-checkpoint-authority
                       "检查点答复即授权", "--checkpoint-authority", "一次答完", "信任这个项目",
                       # wait-honesty-and-briefs
                       "可能已失效", "本次没带 agent-relay 状态",
                       # doctor-and-observer
                       "## 使用注意事项", "doctor --report", "onboard allow", "query stats", "query events",
                       "（有参考意见）",
                       # protocol-contract-v1
                       "## 消息协议", "session-protocol",
                       # relay-presence-and-doubt
                       "送达存疑", "决策收件箱欠回复越来越多",
                       # protocol-contract-v1-3, protocol-contract-v1-4, p0-field-fixes
                       "session-protocol` v2.1",
                       # stall-and-patrol
                       "/loop 5m", "### 常规授权（Claude 线）", "先问」规则可能不生效", "io/snapshots/",
                       # approval-display
                       "### 提请批准怎么读", "回「看 N」展开", "原文取不到", "⚠ 缺证据",
                       # review-nearby
                       "21 A；D1 B；D2 A", "【登记回执】", "返工中（审查第 N 轮）", "0.0.21 改了协作规则段", "0.0.22 改了协作规则段", "不解析【交审】【公共变更请求】【协调通知】", "【负责人转交】",
                       "第一次手动运行之前，定时不会触发", "名字还绑在旧会话上",
                       # patrol-cadence
                       "实际间隔受宿主影响", "宿主没按时触发", "query stats <协作组> [--since 2026-10-17] [--json]",
                       # hub-patrol
                       "决策收件箱会顺带巡视", "重跑一次 `/decision-inbox:hub-setup`",
                       # crew-coordinator-seam
                       "--crew-coordinator", "--local-rules", "CLAUDE.local.md", "不再读 AGENTS.md",
                       # hub-cutover-settings
                       "### 替换已有的决策收件箱", "--start-number", "本插件不读",
                       # transition-compat
                       "### 迁移期：还没接入的会话", "onboard enroll", "hub 编号", "0.0.19"):
            self.assertIn(needle, text)
        for sub in re.findall(r"decision-inbox ([a-z]+)", text):
            self.assertIn(sub, SUBCOMMANDS | {"plugin"}, f"README 用了不存在的子命令 {sub}")


if __name__ == "__main__":
    unittest.main()
