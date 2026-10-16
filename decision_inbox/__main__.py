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


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "store" or argv[1] not in ("init",):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return _init(argv[2])
    except store.InvalidName as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
