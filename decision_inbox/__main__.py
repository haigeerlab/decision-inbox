import argparse
import json
import sys
from pathlib import Path

from decision_inbox import health, mapview, patrol, query, relay, specguard, stophook, store

USAGE = ("用法：python3 -m decision_inbox store <init|show> <协作组>\n"
         "      python3 -m decision_inbox query <lines|flow|item-ids|item> <协作组> ...\n"
         "      python3 -m decision_inbox map <协作组> <线|all> [全部]\n"
         "      python3 -m decision_inbox hook stop --group <协作组> [--session <身份名>]\n"
         "      python3 -m decision_inbox patrol <plan|record|prompt> <协作组> ...")


def _init(name: str) -> int:
    group, created = store.init_group(name)
    if created:
        print(f"已建立协作组 {name}：{group.path}")
    else:
        print(f"协作组 {name} 已存在，未改动任何文件：{group.path}")
    return 0


def _show(name: str) -> int:
    report = store.check(store.open_group(name))
    print(f"协作组：{name}")
    print(f"位置：{report['path']}")
    for rel, state in report["files"].items():
        print(f"  {rel}：{state}")
    print(f"下一个编号：{report['next'] if report['next'] is not None else '无法读取'}")
    sessions = report["sessions"]
    print(f"名册：{sessions if sessions is not None else '无法读取'} 个会话")
    print(f"事件：{report['events']} 条")
    for w in report["warnings"]:
        print(f"⚠ {w}")
    if report["problems"]:
        print("一致性：有问题")
        for msg in report["problems"]:
            print(f"✗ {msg}")
        return 3
    print("一致性：正常")
    return 0


class _RelayUnreadable(Exception):
    pass


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise _RelayUnreadable(f"读不出 agent-relay 原文文件 {path}：{e}") from None


def _parse(parser, text: str):
    try:
        return parser(text)
    except relay.RelayDataError as e:
        raise _RelayUnreadable(str(e)) from None


def _assess(g, args):
    """Facts for /lines and /flow: relay snapshot, each dev line's spec-guard map, patrol's last snapshot."""
    agents = _parse(lambda t: relay.parse_agents(t, relay_version=args.relay_version), _read(args.agents))
    maps = {e["relayName"]: specguard.read_line(e["repo"]) for e in store.roster(g)
            if e["role"] == "dev" and e.get("repo")}
    previous = store.read_state(g, "patrol").get("snapshot")
    now = store.now()
    return now, health.assess(g, now=now, relay=agents, maps=maps, previous=previous), agents, maps


def _query(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox query")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("lines", "flow"):
        p = sub.add_parser(name)
        p.add_argument("group")
        p.add_argument("--agents", required=True)
        p.add_argument("--relay-version")
        if name == "flow":
            p.add_argument("--wakes", required=True)
    for name in ("item-ids", "item"):
        p = sub.add_parser(name)
        p.add_argument("group")
        p.add_argument("number", type=int)
        if name == "item":
            p.add_argument("--status", action="append", default=[])
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        g = store.open_group(args.group)
        if args.command == "lines":
            now, a, agents, maps = _assess(g, args)
            print(query.render_lines(g, now=now, assessment=a, relay=agents, maps=maps))
        elif args.command == "flow":
            wakes = _parse(relay.parse_wake_jobs, _read(args.wakes))
            now, a, agents, _ = _assess(g, args)
            print(query.render_flow(g, now=now, assessment=a, relay=agents, wakes=wakes))
        elif args.command == "item-ids":
            for relay_id in query.item_message_ids(g, args.number):
                print(relay_id)
        else:
            statuses = {}
            for path in args.status:
                st = _parse(relay.parse_message_status, _read(path))
                statuses[st.id] = st
            print(query.render_item(g, args.number, statuses))
    except (store.InvalidName, store.GroupNotFound) as e:
        print(str(e), file=sys.stderr)
        return 2
    except _RelayUnreadable as e:
        print(str(e), file=sys.stderr)
        return 3
    return 0


def _read_line(entry: dict):
    return specguard.read_line(entry["repo"]) if entry.get("repo") else None


def _map(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] != "全部"):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        g = store.open_group(argv[0])
    except (store.InvalidName, store.GroupNotFound) as e:
        print(str(e), file=sys.stderr)
        return 2
    now = store.now()
    lines = [e for e in store.roster(g) if e["role"] == "dev"]
    if argv[1] == "all":
        print(mapview.render_all(g, now, {e["relayName"]: _read_line(e) for e in lines}))
        return 0
    entry = next((e for e in lines if argv[1] in (e["shortName"], e["relayName"])), None)
    read = _read_line(entry) if entry is not None else None
    print(mapview.render_line(g, now, argv[1], read, full=len(argv) == 3))
    return 0


def _hook(argv: list[str]) -> int:
    """Stop hook entry: never fails the host; any problem means "let it stop" (spec 关键决策 6)."""
    try:
        parser = argparse.ArgumentParser(prog="python3 -m decision_inbox hook", add_help=False)
        parser.add_argument("event", choices=["stop"])
        parser.add_argument("--group", required=True)
        parser.add_argument("--session")
        args, _ = parser.parse_known_args(argv)
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("钩子输入不是 JSON 对象")
        d = stophook.decide(store.open_group(args.group), payload, session=args.session)
    except SystemExit:
        print("decision-inbox 停止钩子：参数不对，已放行", file=sys.stderr)
        return 0
    except Exception as e:  # noqa: BLE001 - a broken hook must not trap the session
        print(f"decision-inbox 停止钩子出错，已放行：{e}".replace("\n", " "), file=sys.stderr)
        return 0
    if d.block:
        print(json.dumps({"decision": "block", "reason": d.reason}, ensure_ascii=False))
    elif d.note:
        print(f"decision-inbox 停止钩子放行：{d.note}", file=sys.stderr)
    return 0


def _patrol(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox patrol")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("group")
    p.add_argument("--agents", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--relay-version")
    p = sub.add_parser("record")
    p.add_argument("group")
    p.add_argument("--plan", required=True)
    p.add_argument("--done", nargs="*", default=[])
    p.add_argument("--failed", nargs="*", default=[])
    p = sub.add_parser("prompt")
    p.add_argument("group")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        g = store.open_group(args.group)
    except (store.InvalidName, store.GroupNotFound) as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.command == "prompt":
        print(patrol.prompt(args.group))
        return 0
    if args.command == "plan":
        agents, error = None, None
        try:
            agents = relay.parse_agents(Path(args.agents).read_text(encoding="utf-8"), relay_version=args.relay_version)
        except (OSError, relay.RelayDataError) as e:
            error = str(e)
        maps = {e["relayName"]: specguard.read_line(e["repo"]) for e in store.roster(g)
                if e["role"] == "dev" and e.get("repo")}
        doc = patrol.plan(g, now=store.now(), relay=agents, maps=maps, relay_error=error).to_json()
        Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"actions": doc["actions"]}, ensure_ascii=False, indent=1))
        return 0
    doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    known = {a["id"] for a in doc["actions"]}
    unknown = [i for i in args.done + args.failed if i not in known]
    if unknown:
        print(f"计划里没有这些动作：{'、'.join(unknown)}", file=sys.stderr)
        return 2
    patrol.record(g, doc, done=args.done, failed=args.failed)
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["patrol"]:
        return _patrol(argv[1:])
    if argv[:1] == ["hook"]:
        return _hook(argv[1:])
    if argv[:1] == ["query"]:
        return _query(argv[1:])
    if argv[:1] == ["map"]:
        return _map(argv[1:])
    commands = {"init": _init, "show": _show}
    if len(argv) != 3 or argv[0] != "store" or argv[1] not in commands:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return commands[argv[1]](argv[2])
    except (store.InvalidName, store.GroupNotFound) as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
