import sys

from decision_inbox import store

USAGE = "用法：python3 -m decision_inbox store <init|show> <协作组>"


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


def main(argv: list[str]) -> int:
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
