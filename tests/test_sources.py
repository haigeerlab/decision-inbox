"""approval-display Task 2: originals are read verbatim, or the reason they cannot be is said."""

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from decision_inbox import sources


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


class SourcesCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="di-sources-"))
        self.repo = self.tmp / "repo"
        (self.repo / "spec").mkdir(parents=True)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        self.spec = self.repo / "spec" / "alpha.md"
        self.spec.write_text("# alpha\n第一版\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "one")
        self.first = git(self.repo, "rev-parse", "HEAD")
        self.big = "长文件，" * 40000 + "\n结尾\n"  # > 150KB in UTF-8
        self.spec.write_text(self.big, encoding="utf-8")
        git(self.repo, "commit", "-qam", "two")
        self.second = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class ArtifactTest(SourcesCase):
    def test_whole_text_verbatim(self):
        self.assertGreater(len(self.big.encode("utf-8")), 150_000)
        s = sources.read_artifact(str(self.spec), self.second[:7])
        self.assertTrue(s.ok, s.reason)
        self.assertEqual(s.text, self.big)
        self.assertEqual(sources.read_artifact(str(self.spec), self.first).text, "# alpha\n第一版\n")

    def test_diff_with_previous(self):
        s = sources.read_artifact(str(self.spec), self.second, previous=self.first[:7])
        self.assertTrue(s.ok)
        self.assertIn("-第一版", s.diff)

    def test_unreadable(self):
        cases = {
            (str(self.tmp / "nowhere" / "x.md"), self.second): "不在 git 仓库里",
            (str(self.repo / "spec" / "beta.md"), self.second): "里没有这个文件",
            (str(self.spec), "0000000"): "提交 0000000 不存在",
        }
        outside = self.tmp / "plain"
        outside.mkdir()
        (outside / "a.md").write_text("x", encoding="utf-8")
        cases[(str(outside / "a.md"), self.second)] = "不在 git 仓库里"
        for (path, commit), words in cases.items():
            with self.subTest(path=path, commit=commit):
                s = sources.read_artifact(path, commit)
                self.assertFalse(s.ok)
                self.assertIsNone(s.text)
                self.assertIn(words, s.reason)


class OriginalTest(SourcesCase):
    def write(self, name, data: bytes):
        path = self.tmp / name
        path.write_bytes(data)
        return str(path), "sha256:" + hashlib.sha256(data).hexdigest()[:12]

    def test_verbatim_when_fingerprint_matches(self):
        text = "【交审】\n结束：无\n模块：alpha\n节点：Spec\n要点：原样\n"
        path, fp = self.write("sub.txt", text.encode("utf-8"))
        s = sources.read_original(path, fp)
        self.assertTrue(s.ok, s.reason)
        self.assertEqual(s.text, text)

    def test_unreadable(self):
        path, fp = self.write("sub.txt", "原文".encode("utf-8"))
        latin, latin_fp = self.write("bin.txt", b"\xff\xfe\x00bad")
        cases = [((str(self.tmp / "gone.txt"), fp), "文件不存在"),
                 ((path, "sha256:000000000000"), "指纹对不上"),
                 ((latin, latin_fp), "不是 UTF-8")]
        for (p, f), words in cases:
            with self.subTest(path=p):
                s = sources.read_original(p, f)
                self.assertFalse(s.ok)
                self.assertIsNone(s.text)
                self.assertIn(words, s.reason)
        self.assertIn("现在是 sha256:", sources.read_original(path, "sha256:000000000000").reason)


if __name__ == "__main__":
    unittest.main()
