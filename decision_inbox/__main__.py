import argparse
import json
import os
import sys
from pathlib import Path

from decision_inbox import doctor, health, hub, install, items, mapview, onboard, patrol, query, relay, specguard, stophook, store, view

USAGE = ("用法：python3 -m decision_inbox store <init|show> <协作组>\n"
         "      python3 -m decision_inbox query <lines|flow|item-ids|item|stats|events> <协作组> ...\n"
         "      python3 -m decision_inbox map <协作组> <线|all> [全部]\n"
         "      python3 -m decision_inbox hook stop [--group <协作组>] [--session <身份名>]\n"
         "      python3 -m decision_inbox patrol <plan|record|prompt> <协作组> ...\n"
         "      python3 -m decision_inbox inbox <receive|reply|sent|convention> <协作组> ...\n"
         "      python3 -m decision_inbox view <协作组> [detail <编号>|waits|closed [日期]|invalidated]\n"
         "      python3 -m decision_inbox onboard <hub|join|task|leave|teardown> <协作组> ...\n"
         "      python3 -m decision_inbox shim [--if-installed]\n"
         "      python3 -m decision_inbox whoami [--cwd <目录>]\n"
         "      python3 -m decision_inbox doctor [--group <协作组>] [--json|--report]")


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
    for name in ("stats", "events"):
        p = sub.add_parser(name)
        p.add_argument("group")
        p.add_argument("--since")
        if name == "events":
            p.add_argument("--json", action="store_true", required=True)
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
            if alarm := hub.patrol_alarm(g, now):
                print(alarm)
            print(query.render_flow(g, now=now, assessment=a, relay=agents, wakes=wakes))
        elif args.command == "stats":
            print(query.render_stats(query.stats(g, args.since), args.group, args.since))
        elif args.command == "events":
            print(json.dumps(query.events(g, args.since), ensure_ascii=False, indent=1))
        elif args.command == "item-ids":
            for relay_id in query.item_message_ids(g, args.number):
                print(relay_id)
        else:
            statuses = {} if args.status else None
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
        parser.add_argument("--group")
        parser.add_argument("--session")
        args, _ = parser.parse_known_args(argv)
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("钩子输入不是 JSON 对象")
        session = args.session
        if args.group:
            g = store.open_group(args.group)
        else:
            found = install.locate(str(payload.get("cwd") or ""))
            if not found:
                return 0  # this project has not joined any group
            if len(found) > 1:
                print("decision-inbox 停止钩子放行：工作目录同时属于 " + "、".join(
                    f"{name}/{e['relayName']}" for name, e in found) + "，请检查名册", file=sys.stderr)
                return 0
            g, session = store.open_group(found[0][0]), session or found[0][1]["relayName"]
        d = stophook.decide(g, payload, session=session)
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


def _relay_read(path: str | None, version: str | None):
    """(snapshot or None, "ok"／"absent"／"unreadable", first line of the error)."""
    if not path:
        return None, "absent", None
    try:
        return relay.parse_agents(Path(path).read_text(encoding="utf-8"), relay_version=version), "ok", None
    except (OSError, relay.RelayDataError) as e:
        return None, "unreadable", (str(e).splitlines() or ["原因不明"])[0]


def _relay_or_none(path: str | None, version: str | None):
    """The hub keeps going without agent-relay facts; the main view says so."""
    if not path:
        return None
    try:
        return relay.parse_agents(Path(path).read_text(encoding="utf-8"), relay_version=version)
    except (OSError, relay.RelayDataError):
        return None


def _dev_maps(g) -> dict:
    return {e["relayName"]: specguard.read_line(e["repo"]) for e in store.roster(g)
            if e["role"] == "dev" and e.get("repo")}


def _print_json(doc: dict) -> None:
    print(json.dumps(doc, ensure_ascii=False, indent=1))


def _inbox(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox inbox")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("receive")
    p.add_argument("group")
    p.add_argument("--inbox", required=True)
    p = sub.add_parser("reply")
    p.add_argument("group")
    p.add_argument("--text-file", required=True)
    p.add_argument("--agents")
    p.add_argument("--relay-version")
    p.add_argument("--relayed-from")
    p = sub.add_parser("sent")
    p.add_argument("group")
    p.add_argument("--done", nargs="*", default=[])
    p.add_argument("--failed", nargs="*", default=[])
    p = sub.add_parser("convention")
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
    now = store.now()
    if args.command == "receive":
        try:
            page = relay.parse_inbox(_read(args.inbox))
        except (_RelayUnreadable, relay.RelayDataError) as e:
            print(str(e), file=sys.stderr)
            return 3
        r = hub.receive(g, page, now=now)
        _print_json({"sends": r.sends, "notes": r.notes, "ack": r.ack, "unread": r.unread, "more": r.more})
    elif args.command == "reply":
        text = Path(args.text_file).read_text(encoding="utf-8")
        r = hub.reply(g, text, now=now, relay=_relay_or_none(args.agents, args.relay_version), maps=_dev_maps(g),
                      relayed_from=args.relayed_from)
        _print_json({"show": r.show, "sends": r.sends})
    elif args.command == "sent":
        done = {}
        for pair in args.done:
            out_id, sep, relay_id = pair.partition("=")
            if not sep or not relay_id.isdigit():
                print(f"--done 要写成 out:N=消息编号：{pair}", file=sys.stderr)
                return 2
            done[out_id] = int(relay_id)
        try:
            closed = hub.sent(g, done=done, failed=args.failed, at=now)
        except hub.UnknownOutgoing as e:
            print(f"没有这条待发消息，或已经记过：{e}", file=sys.stderr)
            return 2
        _print_json({"closedTickets": list(closed)})
    else:
        (g.path / "io").mkdir(mode=0o700, exist_ok=True)
        print(hub.convention(args.group, workdir=str(g.path / "io")), end="")
    return 0


def _view(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox view")
    parser.add_argument("group")
    parser.add_argument("what", nargs="*")
    parser.add_argument("--agents")
    parser.add_argument("--outbox")
    parser.add_argument("--relay-version")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    what = args.what
    if what and not (what[0] in ("waits", "invalidated") and len(what) == 1
                     or what[0] == "detail" and len(what) == 2 and what[1].isdigit()
                     or what[0] == "closed" and len(what) in (1, 2)):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        g = store.open_group(args.group)
    except (store.InvalidName, store.GroupNotFound) as e:
        print(str(e), file=sys.stderr)
        return 2
    now = store.now()
    agents, relay_status, relay_error = _relay_read(args.agents, args.relay_version)
    if not what:
        hub_entry = next((e for e in store.roster(g) if e["role"] == "hub"), None)
        if args.outbox and hub_entry is not None:
            try:
                out = relay.parse_outbox(Path(args.outbox).read_text(encoding="utf-8"), sender=hub_entry["relayName"])
                items.update_delivery(g, {m.id: (m.delivery_state, m.acknowledged_at) for m in out.messages}, at=now)
            except (OSError, relay.RelayDataError):
                pass  # delivery progress just stays where it was
        print(hub.main_view(g, now, agents, _dev_maps(g), relay_status=relay_status, relay_error=relay_error))
    elif what[0] == "detail":
        print(view.render_detail(g, int(what[1])))
    elif what[0] == "waits":
        print(view.render_waits(g, now, agents))
    elif what[0] == "closed":
        print(view.render_closed(g, what[1] if len(what) == 2 else hub.today(now)))
    else:
        print(view.render_invalidated(g))
    return 0


def _print_outcome(out, confirm: bool) -> None:
    if out.warnings:
        for warning in out.warnings:
            print(f"⚠ {warning}")
        for note in onboard.CODEX_NOTES if out.codex_unseen else ():
            print(f"  {note}")
    if out.drops:
        state = ("接入时新建，删掉约定块后为空，已删掉这个文件" if confirm
                 else "接入时新建，删掉约定块后为空，确认后会删掉这个文件；确认无误后加 --confirm 再运行")
    elif not out.changed:
        state = "没有变化"
    else:
        state = "已写入" if confirm else "预览，未写入；确认无误后加 --confirm 再运行"
    print(f"规则文件：{out.file}（{state}）")
    print("名册条目：" + json.dumps(out.entry, ensure_ascii=False))
    if out.changed and not out.drops:
        print("改动后的规则文件全文：")
        print(out.after, end="" if out.after.endswith("\n") else "\n")
    if out.steps:
        print("后续步骤：")
        for i, step in enumerate(out.steps, 1):
            print(f"{i}. {step}")
    if out.patrol_prompt:
        print("巡视提示词：")
        print(out.patrol_prompt)


def _onboard(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox onboard")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("hub")
    p.add_argument("group")
    p.add_argument("--relay-name", required=True)
    p.add_argument("--desktop-session", required=True)
    p.add_argument("--project", default=".")
    p.add_argument("--confirm", action="store_true")
    p = sub.add_parser("join")
    p.add_argument("group")
    p.add_argument("--role", required=True)
    p.add_argument("--relay-name", required=True)
    p.add_argument("--short-name", required=True)
    p.add_argument("--host", required=True, choices=list(onboard.RULES_FILES))
    p.add_argument("--line", action="append", default=[])
    p.add_argument("--desktop-session")
    p.add_argument("--project", default=".")
    p.add_argument("--reviewer")
    p.add_argument("--nodes", default="")
    p.add_argument("--session-cwd")
    p.add_argument("--checkpoint-authority", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p = sub.add_parser("task")
    p.add_argument("group")
    p.add_argument("--task-id", required=True)
    for name in ("leave", "teardown"):
        p = sub.add_parser(name)
        p.add_argument("group")
        if name == "leave":
            p.add_argument("--relay-name", required=True)
        p.add_argument("--project")
        p.add_argument("--confirm", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    now = store.now()
    try:
        if args.command == "hub":
            out = onboard.hub(args.group, args.relay_name, args.desktop_session, args.project, args.confirm, now)
        elif args.command == "join":
            nodes = [n for n in args.nodes.split(",") if n]
            out = onboard.join(args.group, args.role, args.relay_name, args.short_name, args.host, args.line,
                               args.desktop_session, args.project, args.reviewer, nodes, args.confirm, now,
                               session_cwd=args.session_cwd, checkpoint_authority=args.checkpoint_authority)
        elif args.command == "task":
            onboard.record_task(args.group, args.task_id, now)
            print(f"已记下巡视任务编号：{args.task_id}")
            return 0
        elif args.command == "leave":
            out = onboard.leave(args.group, args.relay_name, args.project, args.confirm, now)
        else:
            out = onboard.teardown(args.group, args.project, args.confirm, now)
    except (store.StoreError, onboard.JoinError, onboard.BlockConflict) as e:
        print(str(e), file=sys.stderr)
        return 2
    _print_outcome(out, args.confirm)
    return 0


def _whoami(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox whoami")
    parser.add_argument("--cwd", default=".")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    found = install.locate(os.path.abspath(args.cwd))
    if not found:
        print(f"{os.path.abspath(args.cwd)} 没有接入任何协作组", file=sys.stderr)
        return 4
    if len(found) > 1:
        print("工作目录同时属于 " + "、".join(f"{name}/{e['relayName']}" for name, e in found) + "，请检查名册",
              file=sys.stderr)
        return 5
    name, entry = found[0]
    print(json.dumps({"group": name, "relayName": entry["relayName"], "role": entry["role"]}, ensure_ascii=False))
    return 0


def _doctor(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m decision_inbox doctor")
    parser.add_argument("--group", action="append")
    out = parser.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true")
    out.add_argument("--report", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        checks = doctor.run(args.group)
    except (store.InvalidName, store.GroupNotFound) as e:
        print(str(e), file=sys.stderr)
        return 2
    print(doctor.to_json(checks) if args.json else doctor.report(checks) if args.report else doctor.render(checks))
    return 3 if any(c.state == "bad" for c in checks) else 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["doctor"]:
        return _doctor(argv[1:])
    if argv[:1] == ["whoami"]:
        return _whoami(argv[1:])
    if argv[:1] == ["shim"] and argv[1:] in ([], ["--if-installed"]):
        # Silent on purpose: SessionStart runs it in every session.
        install.write_shim(install.plugin_root(), if_installed=argv[1:] == ["--if-installed"])
        return 0
    if argv[:1] == ["onboard"]:
        return _onboard(argv[1:])
    if argv[:1] == ["inbox"]:
        return _inbox(argv[1:])
    if argv[:1] == ["view"]:
        return _view(argv[1:])
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
