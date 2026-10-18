"""`decision-inbox doctor`: is everything installed and wired as the code expects
(see spec/doctor-and-observer.md, decision 1).

Read-only: files are read and nothing is written. The one dependency command run is
module-crew's published read-only sessions output, since only running it shows whether
it can be read (spec/crew-line-status.md decision 5).
Each check says where a problem comes from, so it reaches whoever can fix it.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path

from decision_inbox import crew, deps, hub, install, onboard, protocol, store, view

MARKS = {"ok": "✔", "bad": "✘", "unknown": "？"}


@dataclass(frozen=True)
class Check:
    name: str
    state: str        # ok | bad | unknown
    source: str       # 本插件 | 宿主名 | 依赖插件名
    evidence: str
    fix: str = ""


def _plugin_version(root: Path) -> str | None:
    try:
        return json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def _block_in(text: str) -> str | None:
    lines = text.splitlines(keepends=True)
    try:
        found = onboard._find(lines)
    except onboard.BlockConflict:
        return None
    if found is None:
        return None
    begin, end, _ = found
    return "".join(lines[begin:end + 1])


def _join_command(group: str, entry: dict) -> str:
    cli = install.cli()
    if entry["role"] == "hub":
        return f"{cli} onboard hub {group} …（加 --confirm）"
    flags = "".join(f" {flag}" for key, flag in (("checkpointAuthority", "--checkpoint-authority"),
                                                   ("crewCoordinator", "--crew-coordinator"),
                                                   ("localRules", "--local-rules"))
                    if entry.get(key))
    return (f"{cli} onboard join {group} --role {entry['role']} --relay-name {entry['relayName']}{flags} "
            "…（加 --confirm）")


def _conventions(g: store.Group, group: str) -> list[Check]:
    state = store.read_state(g, onboard.DOMAIN)
    files, left = state.get("files", {}), state.get("left", {})
    hub_relay = next((e["relayName"] for e in store.roster(g) if e["role"] == "hub"), "")
    out = []
    for entry in store.roster(g):
        name = f"约定块：{entry['shortName']}"
        if entry["relayName"] in left:
            continue
        if entry.get("legacyFormat"):
            out.append(Check(name, "ok", "本插件", "只登记，不写约定块（迁移期旧格式会话）"))
            continue
        rules = files.get(entry["relayName"])
        if rules is None:
            out.append(Check(name, "unknown", "本插件", "接入记录里没有它的规则文件"))
            continue
        try:
            text = Path(rules).read_text(encoding="utf-8")
        except OSError as e:
            out.append(Check(name, "bad", "本插件", f"规则文件读不出：{rules}（{e}）", _join_command(group, entry)))
            continue
        current = _block_in(text)
        want = onboard.block(entry["role"], group, hub_relay, bool(entry.get("checkpointAuthority")),
                             bool(entry.get("crewCoordinator")))
        if current is None:
            out.append(Check(name, "bad", "本插件", f"{rules} 里没有 decision-inbox 约定块", _join_command(group, entry)))
        elif current != want:
            out.append(Check(name, "bad", "本插件", f"{rules} 里的约定块不是当前版本",
                             "重跑接入命令：" + _join_command(group, entry)))
        else:
            out.append(Check(name, "ok", "本插件", str(rules)))
        if entry.get("host") == "codex-desktop" and current is not None:
            unseen = onboard.codex_loads(rules, Path(rules).parent, rules_text=text)
            out.append(Check(f"Codex 加载约定块：{entry['shortName']}", "bad" if unseen else "ok", "Codex",
                             "；".join(unseen) or f"在 {Path(rules).parent} 开的 Codex 会话能加载",
                             "按上面的说明调整后，在 Codex 里新开任务" if unseen else ""))
    return out


def _shim() -> Check:
    path = install.shim_path()
    here = install.plugin_root()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Check("转发脚本", "bad", "本插件", f"没有转发脚本：{path}", f"运行 {here / 'bin' / 'decision-inbox'} shim")
    m = re.search(r"^exec (.+) \"\$@\"$", text, re.M)
    target = Path(shlex.split(m.group(1))[0]) if m else None
    if target is None:
        return Check("转发脚本", "bad", "本插件", f"{path} 的内容看不懂", f"运行 {here / 'bin' / 'decision-inbox'} shim")
    root = target.parent.parent
    version = _plugin_version(root)
    if os.path.realpath(root) != os.path.realpath(here):
        return Check("转发脚本", "bad", "本插件",
                     f"{path} 指向 {root}（版本 {version or '未知'}），本次运行的代码在 {here}（版本 {_plugin_version(here) or '未知'}）",
                     f"运行 {here / 'bin' / 'decision-inbox'} shim 改回；开发环境里已装插件的启动钩子会把它改回已装版本")
    return Check("转发脚本", "ok", "本插件", f"{path} → {root}（版本 {version or '未知'}）")


def _patrol(g: store.Group, now: str) -> Check:
    task = store.read_state(g, onboard.DOMAIN).get("patrolTask")
    if not task:
        return Check("巡视", "unknown", "本插件", "没有登记巡视任务", "按 onboard hub 打印的步骤建巡视任务后运行 onboard task")
    alarm = hub.patrol_alarm(g, now)
    if alarm:
        return Check("巡视", "bad", "Claude 桌面版", alarm.lstrip("⚠ ").split("：")[0],
                     hub.patrol_fix(task))
    last = store.read_state(g, "patrol").get("lastRunAt")
    return Check("巡视", "ok", "本插件", f"最近一轮 {view._minutes(now, last)} 分钟前" if last else "刚登记，还没到第一轮")


def codex_config() -> Path:
    override = os.environ.get("DECISION_INBOX_CODEX_CONFIG")
    return Path(override) if override else Path.home() / ".codex" / "config.toml"


_HOOK_SECTION = re.compile(r'^\[hooks\.state\."(decision-inbox@[^"]+)"\]\s*$')


def _codex_trust() -> Check:
    """Codex keeps hook trust as [hooks.state."<plugin>@<market>:<file>:<event>:..."] with trusted_hash/enabled."""
    path = codex_config()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return Check("Codex 钩子信任", "unknown", "Codex", f"读不到 {path}")
    sections, current = {}, None
    for line in lines:
        m = _HOOK_SECTION.match(line)
        if m:
            current = sections.setdefault(m.group(1), {})
        elif line.startswith("["):
            current = None
        elif current is not None and "=" in line:
            key, value = (s.strip() for s in line.split("=", 1))
            current[key] = value
    if not sections:
        return Check("Codex 钩子信任", "unknown", "Codex", f"{path} 里没有 decision-inbox 钩子的信任记录",
                     "在 Codex 里信任一次 decision-inbox 插件自带的停止钩子")
    bad = [k for k, v in sections.items() if "trusted_hash" not in v or v.get("enabled") == "false"]
    if bad:
        return Check("Codex 钩子信任", "bad", "Codex", f"没信任或已停用：{'、'.join(bad)}",
                     "在 Codex 里重新信任 decision-inbox 插件自带的停止钩子")
    return Check("Codex 钩子信任", "ok", "Codex", f"{len(sections)} 个钩子已信任")


_PLUGIN_SECTION = re.compile(r'^\[plugins\."decision-inbox@([^"]+)"\]\s*$')
INSTALL_SOURCE = "Claude Code／Codex 安装"


def _cached_version(path: Path) -> str:
    for manifest in (".codex-plugin", ".claude-plugin"):
        version = _plugin_version_in(path / manifest / "plugin.json")
        if version:
            return version
    return path.name


def _plugin_version_in(manifest: Path) -> str | None:
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _codex_install():
    """(market, versions) from Codex's config and plugin cache; None when Codex has it off; str when unreadable."""
    path = codex_config()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    except OSError as e:
        return f"读不到 {path}（{e}）"
    market, enabled = None, True
    for line in lines:
        m = _PLUGIN_SECTION.match(line)
        if m:
            market, enabled = m.group(1), True
        elif market is not None and line.startswith("["):
            break
        elif market is not None and "=" in line:
            key, value = (x.strip() for x in line.split("=", 1))
            if key == "enabled":
                enabled = value != "false"
    if market is None or not enabled:
        return None
    cache = path.parent / "plugins" / "cache" / market / "decision-inbox"
    versions = sorted(_cached_version(d) for d in cache.iterdir() if d.is_dir()) if cache.is_dir() else []
    if not versions:
        return f"Codex 启用了 decision-inbox@{market}，但 {cache} 里没有可读的版本"
    return market, versions


def _host_versions() -> Check:
    """Claude and Codex each load their own installed copy; they should be the same version (rehearsal-fixes)."""
    name = "Claude、Codex 两边的版本"
    codex = _codex_install()
    if isinstance(codex, str):
        return Check(name, "unknown", INSTALL_SOURCE, codex)
    found = deps.find("decision-inbox")
    claude = None if isinstance(found, deps.NotFound) else found.version
    codex_versions = codex[1] if codex else []
    evidence = f"Claude {claude or '没装'}；Codex {'、'.join(codex_versions) or '没装'}"
    if len(codex_versions) > 1 or (claude and codex_versions and codex_versions != [claude]):
        market = codex[0]
        return Check(name, "bad", INSTALL_SOURCE, evidence,
                     f"在终端运行 codex plugin remove decision-inbox@{market}，再 codex plugin add decision-inbox@{market}；"
                     "Claude 侧在插件管理里更新 decision-inbox，或按 README「固定副本安装」重装；装好后重开会话")
    return Check(name, "ok", INSTALL_SOURCE, evidence)


_OPTIONAL = {"spec-guard", "delegate"}


def _contract(d: deps.Dependency, text: str) -> tuple[str, str]:
    """module-crew names the session-protocol version it speaks; a different major is a mismatch."""
    theirs = str(d.interface.data.get("contract", ""))
    if not theirs:
        return "ok", text
    text += f"，契约 {theirs}"
    if theirs.split(".")[0] != protocol.CONTRACT_VERSION.split(".")[0]:
        return "bad", text
    if theirs != protocol.CONTRACT_VERSION:
        text += f"（本插件按 {protocol.CONTRACT_VERSION}）"
    return "ok", text


def _dependency(name: str, required: bool = False) -> Check:
    d = deps.dependency(name)
    label = f"依赖：{name}"
    if d.version is None:
        if name == "module-crew" and required:
            return Check(label, "bad", name, d.reason, "名册里有并行开发协调会话，安装 module-crew 才看得到各模块状态")
        if name in _OPTIONAL or name == "module-crew":
            return Check(label, "ok", name, f"{d.reason}（可选）")
        return Check(label, "bad", name, d.reason, "安装 agent-relay，收件枢纽和各会话靠它收发消息")
    text = deps.describe(d)
    if name == "module-crew" and d.interface.state == "ok":
        state, text = _contract(d, text)
        if state == "bad":
            return Check(label, "bad", name, text, f"换用与 session-protocol {protocol.CONTRACT_VERSION} 同主版本的 module-crew")
    if d.interface.state == "ok":
        fix = f"能不能用以 {deps.delegate_command(d, 'doctor')} 为准" if name == "delegate" else ""
        return Check(label, "ok", name, text, fix)
    if d.interface.state == "incompatible":
        return Check(label, "bad", name, text, f"把 {name} 换到本插件支持的接口版本，或升级本插件")
    fix = "升级到提供 interface.json 的版本"
    if name == "delegate":
        fix += f"；能不能用以 {deps.delegate_command(d, 'doctor')} 为准"
    return Check(label, "unknown", name, text, fix)


def _crew_output(entry: dict) -> Check:
    read = crew.read_modules(entry["repo"])
    name = f"module-crew 出口：{entry['shortName']}"
    if read.status == "ok":
        return Check(name, "ok", "module-crew", f"读到 {len(read.modules)} 个模块会话")
    return Check(name, "bad", "module-crew", read.reason,
                 f"按原因处理；处理好之前，主视图里这条线显示「模块状态未知」（在 {entry['repo']} 运行 sessions --json）")


def _groups(names) -> list[str]:
    if names:
        return list(names)
    root = store.root_dir()
    return sorted(p.name for p in root.iterdir() if (p / "group.json").is_file()) if root.is_dir() else []


def run(groups=None, now: str | None = None) -> list[Check]:
    now = now or store.now()
    out = [_shim()]
    codex = False
    coordinators = []
    for group in _groups(groups):
        g = store.open_group(group)
        out += _conventions(g, group)
        out.append(_patrol(g, now))
        coordinators += crew.coordinators(g)
        left = store.read_state(g, onboard.DOMAIN).get("left", {})
        codex |= any(e.get("host") == "codex-desktop" and e["relayName"] not in left for e in store.roster(g))
    if codex:
        out.append(_codex_trust())
    out.append(_host_versions())
    out += [_dependency(n) for n in ("agent-relay", "spec-guard", "delegate")]
    out.append(_dependency("module-crew", required=bool(coordinators)))
    out += [_crew_output(e) for e in coordinators]
    return out


def render(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"{MARKS[c.state]} {c.name}：{c.evidence}（来源：{c.source}）")
        if c.fix and c.state != "ok":
            lines.append(f"   怎么做：{c.fix}")
    bad = sum(c.state == "bad" for c in checks)
    unknown = sum(c.state == "unknown" for c in checks)
    lines.append(f"共 {len(checks)} 项：异常 {bad}，未知 {unknown}")
    return "\n".join(lines)


def to_json(checks: list[Check]) -> str:
    return json.dumps({"schemaVersion": 1, "checks": [asdict(c) for c in checks]}, ensure_ascii=False, indent=1)


def report(checks: list[Check]) -> str:
    """A report to forward to whoever owns the problem: findings, sources and versions, no message bodies."""
    here = install.plugin_root()
    versions = [f"decision-inbox {_plugin_version(here) or '未知'}"]
    versions += [c.evidence for c in checks if c.name.startswith("依赖：")]
    problems = [c for c in checks if c.state != "ok"]
    lines = ["decision-inbox 异常报告", "", "版本：", *[f"- {v}" for v in versions], ""]
    if not problems:
        lines.append("没有发现异常。")
    for c in problems:
        lines += [f"【{'异常' if c.state == 'bad' else '未知'}】{c.name}（来源：{c.source}）",
                  f"- 现象：{c.evidence}"] + ([f"- 建议：{c.fix}"] if c.fix else [])
    return "\n".join(lines)
