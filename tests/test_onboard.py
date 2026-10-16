import unittest

from helpers import TempHomeTestCase

from decision_inbox import onboard

DEV = "<!-- BEGIN decision-inbox dev -->\n## dev rules\n<!-- END decision-inbox dev -->\n"
DEV2 = "<!-- BEGIN decision-inbox dev -->\n## dev rules v2\nmore\n<!-- END decision-inbox dev -->\n"
OWNER = "<!-- BEGIN decision-inbox owner -->\n## owner rules\n<!-- END decision-inbox owner -->\n"


class PlaceTest(unittest.TestCase):
    def test_empty_file(self):
        self.assertEqual(onboard.place("", "dev", DEV), DEV)

    def test_appended_after_existing_content(self):
        text = "# 项目规则\n\n- 用中文\n"
        self.assertEqual(onboard.place(text, "dev", DEV), text + "\n" + DEV)

    def test_no_trailing_newline_gets_one(self):
        self.assertEqual(onboard.place("# x", "dev", DEV), "# x\n\n" + DEV)

    def test_same_role_replaced_in_place(self):
        for before, after in (("", ""), ("# 头\n\n", ""), ("", "\n## 尾\n"), ("# 头\n\n", "\n## 尾\n")):
            text = before + DEV + after
            self.assertEqual(onboard.place(text, "dev", DEV2), before + DEV2 + after)

    def test_other_role_or_broken_markers_conflict(self):
        for text in ("# x\n\n" + OWNER,
                     "<!-- BEGIN decision-inbox dev -->\n半截\n",
                     "孤立\n<!-- END decision-inbox dev -->\n",
                     DEV + "\n" + DEV,
                     "<!-- BEGIN decision-inbox dev -->\n<!-- END decision-inbox owner -->\n"):
            with self.assertRaises(onboard.BlockConflict):
                onboard.place(text, "dev", DEV2)

    def test_marker_must_be_whole_line(self):
        text = "说明：标记写作 <!-- BEGIN decision-inbox dev --> 这样\n"
        self.assertEqual(onboard.place(text, "dev", DEV), text + "\n" + DEV)


class StripTest(unittest.TestCase):
    def test_round_trip_keeps_everything_else(self):
        for text in ("", "# 项目规则\n\n- 用中文\n", "a\n\n\nb\n"):
            self.assertEqual(onboard.strip(onboard.place(text, "dev", DEV)), (text, True))

    def test_round_trip_without_trailing_newline_only_adds_it(self):
        self.assertEqual(onboard.strip(onboard.place("# x", "dev", DEV)), ("# x\n", True))

    def test_block_in_the_middle(self):
        text = "# 头\n\n" + OWNER + "\n## 尾\n"
        self.assertEqual(onboard.strip(text), ("# 头\n\n## 尾\n", True))

    def test_block_at_start(self):
        self.assertEqual(onboard.strip(DEV + "\n## 尾\n"), ("## 尾\n", True))

    def test_no_block_unchanged(self):
        self.assertEqual(onboard.strip("# 头\n"), ("# 头\n", False))

    def test_broken_markers_conflict(self):
        with self.assertRaises(onboard.BlockConflict):
            onboard.strip("<!-- BEGIN decision-inbox dev -->\n半截\n")


if __name__ == "__main__":
    unittest.main()
