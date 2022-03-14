import unittest
import sys
import os
import json

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
sys.path.insert(0, PROJECT_DIR)

from module.config import ssh_login
from module.config import command_kind
from module.config import qmp_config
from module.config import qmp_command
from module.config import qmp_reply
from module.config import qmp_request
from module.config import qmp_response


class test_qmp(unittest.TestCase):
    def __init__(self, methodName: str = ...) -> None:
        self.cmdline_json:json = {"command-line" : "device_add usb-winusb,id=winusb-01,pcap=winusb-01.pcap" }
        super().__init__(methodName)

    def test_qmp_command(self):
        qmp_cmd = qmp_command(10010, "human-monitor-command", self.cmdline_json, False)

        self.assertEqual(qmp_cmd.taskid, 10010)
        self.assertEqual(qmp_cmd.execute, "human-monitor-command")
        self.assertEqual(qmp_cmd.argsjson, self.cmdline_json)

    def test_qmp_config(self):
        qmp_cmd = qmp_command(10010, "human-monitor-command", self.cmdline_json, False)
        qmp_cfg = qmp_config(qmp_cmd.toJSON())

        self.assertEqual(qmp_cfg.cmd.taskid, 10010)
        self.assertEqual(qmp_cfg.cmd.execute, "human-monitor-command")
        self.assertEqual(qmp_cfg.cmd.argsjson, self.cmdline_json)

if __name__ == '__main__':
    unittest.main()
