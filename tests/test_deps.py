import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from decision_inbox import deps


class DepsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="di-deps-"))
        self.records = self.tmp / "installed_plugins.json"
        self._old = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.records)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        else:
            os.environ["DECISION_INBOX_PLUGINS_FILE"] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self, plugin, version, interface=None):
        root = self.tmp / plugin / version
        root.mkdir(parents=True)
        if interface is not None:
            (root / "interface.json").write_text(interface, encoding="utf-8")
        entries = json.loads(self.records.read_text()) if self.records.exists() else {"version": 2, "plugins": {}}
        entries["plugins"][f"{plugin}@m"] = [{"scope": "user", "installPath": str(root), "version": version}]
        self.records.write_text(json.dumps(entries), encoding="utf-8")
        return root


DELEGATE = json.dumps({"interface": "1.0", "review": {"command": "/delegate:review"},
                       "doctor": {"command": "/delegate:doctor"}})


class DependencyTest(DepsCase):
    def test_delegate_states(self):
        self.install("delegate", "0.5.3", DELEGATE)
        d = deps.dependency("delegate")
        self.assertEqual((d.version, d.interface.state, d.interface.version), ("0.5.3", "ok", "1.0"))
        self.install("delegate", "0.5.2")
        d = deps.dependency("delegate")
        self.assertEqual((d.version, d.interface.state), ("0.5.2", "absent"))
        self.assertEqual(deps.describe(d), "delegate 0.5.2：读不到接口说明（可能早于提供 interface.json 的版本）")
        self.install("delegate", "9.0.0", json.dumps({"interface": "2.0"}))
        d = deps.dependency("delegate")
        self.assertEqual(d.interface.state, "incompatible")
        self.assertEqual(deps.describe(d), "delegate 9.0.0：接口版本 2.0，本插件只认 1.x")

    def test_agent_relay_major_two(self):
        self.install("agent-relay", "0.8.2", json.dumps({"interface": "2.5", "status": ["python3"]}))
        d = deps.dependency("agent-relay")
        self.assertEqual((d.interface.state, deps.describe(d)), ("ok", "agent-relay 0.8.2：接口 2.5，兼容"))

    def test_not_installed_is_its_own_wording(self):
        self.install("spec-guard", "0.67.0")
        d = deps.dependency("delegate")
        self.assertIsNone(d.version)
        self.assertEqual(deps.describe(d), "delegate：本机没有安装 delegate")

    def test_delegate_commands(self):
        self.install("delegate", "0.5.3", json.dumps({"interface": "1.0", "review": {"command": "/delegate:review"},
                                                       "doctor": {"command": "rm -rf /"}}))
        d = deps.dependency("delegate")
        self.assertEqual(deps.delegate_command(d, "review"), "/delegate:review")
        self.assertEqual(deps.delegate_command(d, "doctor"), "/delegate:doctor")   # bad value -> default
