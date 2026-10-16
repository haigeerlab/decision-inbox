import sys


def main(argv: list[str]) -> int:
    print("用法：python3 -m decision_inbox store <init|show> <协作组>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
