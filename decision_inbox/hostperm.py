"""Read-only check of a line's host permissions against what its repository needs (spec/host-permission-check.md,
spec/permission-closeout.md).

R21 DI-4: Codex (sandbox mode, network, project trust, the project's .codex/config.toml) and Claude
(this plugin's install rules) are read, never written; the user changes them, or clicks in the session.
Codex's layering follows openai/codex's config loader: a project .codex/config.toml counts only when the
project is trusted. Only the few keys used here are read, line by line (no TOML parser on Python 3.10).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from decision_inbox import onboard

_TABLE = re.compile(r"^\[(.+)\]\s*$")
_KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$')
_PROJECT = re.compile(r'^projects\."(.+)"$')


@dataclass(frozen=True)
class CodexFacts:
    write: bool | None
    network: bool | None
    trusted: bool | None
    network_source: str          # 全局配置 | 项目配置 | 沙箱模式 | "" when network is off or unknown
    reason: str | None           # why the facts are unknown


@dataclass(frozen=True)
class ClaudeFacts:
    installs_allowed: bool | None
    retired: list = field(default_factory=list)
    reason: str | None = None
    allow: list = field(default_factory=list)


@dataclass(frozen=True)
class ProjectNeeds:
    installs: bool          # the repository root has a dependency manifest
    dev: str | None         # the dev-server rule to allow when package.json has a `dev` script


@dataclass(frozen=True)
class Result:
    state: str                   # ok | bad | unknown
    evidence: str
    fix: str = ""


def _value(raw: str):
    raw = raw.split("#", 1)[0].strip() if not raw.startswith('"') else raw
    if raw in ("true", "false"):
        return raw == "true"
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    return raw


def _read_toml(path: Path) -> dict[str, dict[str, object]]:
    """{table: {key: value}} for simple `key = value` lines; the top level is the table ""."""
    tables: dict[str, dict[str, object]] = {"": {}}
    current = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if m := _TABLE.match(line):
            current = m.group(1).strip()
            tables.setdefault(current, {})
        elif m := _KEY.match(line):
            tables[current][m.group(1)] = _value(m.group(2))
    return tables


def _trusted(tables: dict, repo: Path) -> bool:
    for name, keys in tables.items():
        m = _PROJECT.match(name)
        if m and keys.get("trust_level") == "trusted":
            root = Path(m.group(1)).resolve()  # /var -> /private/var on macOS, as the repo path is
            if repo == root or root in repo.parents:
                return True
    return False


def codex_facts(repo: str, config_path: Path) -> CodexFacts:
    """What a Codex session opened in `repo` may do, from the global and the project config."""
    here = Path(repo).resolve()
    try:
        tables = _read_toml(Path(config_path))
    except (OSError, UnicodeDecodeError) as e:
        return CodexFacts(None, None, None, "", f"读不到 {config_path}（{e.__class__.__name__}）")
    trusted = _trusted(tables, here)
    project = {}
    local = here / ".codex" / "config.toml"
    if trusted and local.is_file():
        try:
            project = _read_toml(local)
        except (OSError, UnicodeDecodeError) as e:
            return CodexFacts(None, None, trusted, "", f"读不到 {local}（{e.__class__.__name__}）")
    mode = project.get("", {}).get("sandbox_mode") or tables[""].get("sandbox_mode")
    if mode not in ("read-only", "workspace-write", "danger-full-access"):
        return CodexFacts(None, None, trusted, "", f"{config_path} 里没有认得出的 sandbox_mode")
    if mode == "danger-full-access":
        return CodexFacts(True, True, trusted, "沙箱模式", None)
    if mode == "read-only":
        return CodexFacts(False, False, trusted, "", None)
    local_net = project.get("sandbox_workspace_write", {}).get("network_access")
    if local_net is not None:
        return CodexFacts(True, local_net is True, trusted, "项目配置" if local_net is True else "", None)
    global_net = tables.get("sandbox_workspace_write", {}).get("network_access") is True
    return CodexFacts(True, global_net, trusted, "全局配置" if global_net else "", None)


# permission-closeout: adding a package is allowed now; lockfile-only rules (npm ci …) no longer count as enough
INSTALL_ALLOW = ("Bash(npm install *)", "Bash(pnpm add *)", "Bash(yarn add *)", "Bash(uv add *)")


def claude_facts(repo: str) -> ClaudeFacts:
    """Whether this plugin's install rules are there (scope-authority-defaults) and old ask rules are gone."""
    allow, ask = [], []
    for name in ("settings.json", "settings.local.json"):
        path = Path(repo) / ".claude" / name
        if not path.is_file():
            continue
        try:
            perms = json.loads(path.read_text(encoding="utf-8")).get("permissions", {})
            allow += list(perms.get("allow", []))
            ask += list(perms.get("ask", []))
        except (OSError, ValueError, AttributeError, TypeError) as e:
            return ClaudeFacts(None, [], f"{path} 读不懂（{e.__class__.__name__}）")
    return ClaudeFacts(any(r in allow for r in INSTALL_ALLOW), [r for r in onboard.RETIRED_ASK if r in ask],
                       allow=allow)


MANIFESTS = ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "pyproject.toml", "uv.lock")


def project_needs(repo: str) -> ProjectNeeds:
    """What building this repository installs, from its root only (permission-closeout; the Plan is not read)."""
    root = Path(repo)
    installs = any((root / name).is_file() for name in MANIFESTS) or any(root.glob("requirements*.txt"))
    return ProjectNeeds(installs, onboard.dev_server_rule(root))


_OPTION_B = "B 不改：开发线碰到时按「去会话操作」上报，决策收件箱最上面一栏会提醒你去那个会话点"


def _codex_text(f: CodexFacts) -> str:
    write = "可写工作区" if f.write else "不能写工作区"
    net = f"可联网（{f.network_source}）" if f.network else "不能联网"
    return f"Codex {write}、{net}、项目{'已信任' if f.trusted else '未信任'}"


def _command(rule: str) -> str:
    return rule[len("Bash("):-1]


def compare(host: str, repo: str, codex: CodexFacts | None, claude: ClaudeFacts | None, needs: ProjectNeeds) -> Result:
    """The host facts against what the repository needs; options A (the user changes it) and B (click when asked)."""
    if host == "codex-desktop":
        if codex is None or codex.reason:
            return Result("unknown", codex.reason if codex else "没读 Codex 配置")
        text = _codex_text(codex)
        if not needs.installs:
            return Result("ok", f"{text}；仓库根目录没有依赖清单，不用装依赖")
        if codex.network:
            return Result("ok", text)
        browser = "；有开发服务，界面自验要用的 Playwright 之类可能下载不了浏览器" if needs.dev else ""
        first = "" if codex.trusted else "先在 Codex 里信任这个项目，再"
        fix = (f"A 你自己改：{first}在 {repo}/.codex/config.toml 写两行 [sandbox_workspace_write] 和 "
               "network_access = true（依据 openai/codex 源码，Codex 桌面应用没实测，改完在开发会话里试一次；"
               f"不改 ~/.codex/config.toml）；{_OPTION_B}")
        return Result("bad", f"{text}，但仓库有依赖清单，要装依赖{browser}", fix)
    if claude is None or claude.reason:
        return Result("unknown", claude.reason if claude else "没读 Claude 设置")
    text = "Claude 放行装依赖与加新包" if claude.installs_allowed else "Claude 没有放行加新包的规则"
    if claude.retired:
        text += f"，还留着旧版写的先问规则 {'、'.join(claude.retired)}"
    missing_dev = needs.dev is not None and needs.dev not in claude.allow
    if missing_dev:
        text += f"，开发服务命令 {_command(needs.dev)} 没放行（界面自验每次都要你点）"
    if not needs.installs:
        return Result("ok", f"{text}；仓库根目录没有依赖清单，不用装依赖")
    if claude.installs_allowed and not claude.retired and not missing_dev:
        return Result("ok", text)
    fix = f"A 你自己改：在这条线的会话里重跑接入，确认加上放行规则、删掉旧的先问规则；{_OPTION_B}"
    return Result("bad", f"{text}，而仓库有依赖清单，要装依赖", fix)
