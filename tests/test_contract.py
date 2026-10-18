"""Conformance with the shared session-protocol contract (see spec/protocol-contract-v1.md).

The contract's fixtures are copied verbatim into tests/fixtures/session-protocol/<version>/;
this plugin's own parser and generators must reproduce every expected result.
"""

import hashlib
import json
import unittest
from pathlib import Path

from decision_inbox import protocol

VERSION = "v1.7"
HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fixtures" / "session-protocol" / VERSION
ORIGINAL = HERE / "fixtures" / "protocol"
# Kinds this plugin only generates (the hub sends them, other sessions read them).
GENERATE_ONLY = {"answer-notice"}
# Kinds added in v1.1 for module-crew; this plugin neither parses nor generates them (protocol-contract-v1-3).
NOT_PARSED = {"review-request", "shared-change-request", "coordination-notice",
              # v1.6: owner -> dev/coordinator; the hub never receives it (transition-compat)
              "owner-handoff"}
# v1.6: a coordinator relaying the hub's answer to its own dev lines; the hub never receives these.
NOT_PARSED_PREFIX = ("user-reply/relay-",)


def skipped(path) -> bool:
    name = path.relative_to(CONTRACT).as_posix()
    return path.parent.name in NOT_PARSED or name.startswith(NOT_PARSED_PREFIX)


def to_contract(m: protocol.Message) -> dict:
    """A parsed message in the contract's field names (PROTOCOL.md section 12)."""
    c = m.conclusion
    return {
        "type": m.kind,
        "valid": not m.problems,
        "replyTo": m.reply_to,
        "end": {"present": m.ends.present, "items": list(m.ends.ids), "none": m.ends.none,
                "unnumberedReason": m.ends.unnumbered_reason},
        "markers": [{"kind": k, "item": n} for k, n in m.markers],
        "item": m.item,
        "fields": m.fields,
        "options": [{"letter": o.letter, "text": o.text, "consequence": o.consequence} for o in m.options],
        "recommended": m.recommended,
        "suggestedReply": m.suggested_reply,
        "fullyStopped": m.fully_stopped,
        "linesInScope": list(m.lines_in_scope),
        "scopes": m.scopes,
        "reviewLine": {"status": m.review.status, "adviceCount": m.review.advice_count, "ref": m.review.ref},
        "conclusion": None if c is None else {
            "ref": c.ref, "node": c.node, "submitter": c.submitter, "verdict": c.verdict,
            "adviceCount": c.advice_count, "module": c.module},
        "problems": [p.code for p in m.problems],
        "hints": [h.code for h in m.hints],
    }


def generate(kind: str, a: dict) -> str:
    if kind == "user-reply":
        return protocol.format_user_reply(a["item"], a["original"], a["answeredAt"], a["optionText"],
                                          a["sourceRelayId"])
    if kind == "answer-notice":
        return protocol.format_answer_notice(a["item"], a["ownerShort"], a["original"], a["answeredAt"],
                                             a["sourceRelayId"])
    if kind == "multiline-user-reply":
        source = (CONTRACT / a["waitUserFixture"]).read_text(encoding="utf-8")
        replies = protocol.format_multiline_replies(a["item"], a["sender"], a["original"], a["answeredAt"],
                                                    source, a["sourceRelayId"])
        return replies[a["forSession"]]
    raise AssertionError(f"契约里有本插件不认识的生成类型：{kind}")


def cases():
    return sorted(CONTRACT.glob("*/*.json"))


class FingerprintTest(unittest.TestCase):
    def test_copy_matches_sha256sums(self):
        listed = {}
        for line in (CONTRACT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, name = line.split(maxsplit=1)
            listed[name.removeprefix("./")] = digest
        present = {p.relative_to(CONTRACT).as_posix() for p in CONTRACT.glob("*/*") if p.is_file()}
        self.assertEqual(present, set(listed), "样例副本里多了或少了文件")
        for name, digest in listed.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((CONTRACT / name).read_bytes()).hexdigest(), digest,
                                 f"{name} 和契约 {VERSION} 的指纹对不上")

    def test_source(self):
        self.assertEqual((CONTRACT / "SOURCE").read_text(encoding="utf-8").split(),
                         ["session-protocol", VERSION, "1e14a49"])


class ConformanceTest(unittest.TestCase):
    def test_counts(self):
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in cases()]
        self.assertEqual(sum("parse" in d for d in docs), 63)
        self.assertEqual(sum("generate" in d for d in docs), 6)
        self.assertEqual(len([p for p in cases() if skipped(p)]), 26,
                         "契约给不解析的类型加了样例，确认本插件是否仍不需要它们")

    def test_parse(self):
        for path in cases():
            expected = json.loads(path.read_text(encoding="utf-8")).get("parse")
            if expected is None or path.parent.name in GENERATE_ONLY or skipped(path):
                continue
            got = to_contract(protocol.parse(path.with_suffix(".txt").read_text(encoding="utf-8")))
            for key, want in expected.items():
                with self.subTest(sample=path.relative_to(CONTRACT).as_posix(), key=key):
                    self.assertEqual(got[key], want)

    def test_generate(self):
        for path in cases():
            spec = json.loads(path.read_text(encoding="utf-8")).get("generate")
            if spec is None or skipped(path):
                continue
            with self.subTest(sample=path.relative_to(CONTRACT).as_posix()):
                self.assertEqual(generate(spec["kind"], spec["inputs"]),
                                 path.with_suffix(".txt").read_text(encoding="utf-8"))

    def test_original_samples_are_in_the_contract(self):
        pairs = {"wait-user.txt": "wait-user/basic.txt", "wait-user-multiline.txt": "wait-user/multiline.txt",
                 "wait-session.txt": "wait-session/basic.txt", "resumed.txt": "resumed/basic.txt",
                 "review-conclusion.txt": "review-conclusion/basic.txt"}
        self.assertEqual({p.name for p in ORIGINAL.glob("*.txt")}, set(pairs))
        for mine, theirs in pairs.items():
            with self.subTest(sample=mine):
                self.assertEqual((ORIGINAL / mine).read_bytes(), (CONTRACT / theirs).read_bytes())


if __name__ == "__main__":
    unittest.main()
