import unittest
import sys
import os
import json

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
sys.path.insert(0, PROJECT_DIR)

from module.config import os_kind, ssh_login
from module.config import command_kind
from module.config import start_config
from module.config import start_command
from module.config import start_reply
from module.config import start_request
from module.config import start_response


class test_start(unittest.TestCase):
    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)
        self.program = "shutdown"
        self.arguments =  ['-s', '-t', '0']
        self.longlife = 10
        self.ssh_login = ssh_login("dougpuob", "dougpuob")

    def test_start_command(self):
        start_cmd = start_command(self.program, self.arguments, self.longlife, self.ssh_login)

        self.assertEqual(start_cmd.program, self.program)
        self.assertEqual(start_cmd.arguments[0], self.arguments[0])
        self.assertEqual(start_cmd.arguments[1], self.arguments[1])
        self.assertEqual(start_cmd.arguments[2], self.arguments[2])
        self.assertEqual(start_cmd.longlife, self.longlife)
        self.assertEqual(start_cmd.ssh_login, self.ssh_login)

    def test_start_config(self):
        json_data = { "program"   : self.program,
                      "arguments" : self.arguments,
                      "longlife"  : self.longlife,
                      "ssh_login" : self.ssh_login.toJSON() }

        start_cfg = start_config(json_data)

        self.assertEqual(start_cfg.cmd.toJSON(), json_data)
        self.assertEqual(start_cfg.cmd.program, self.program)
        self.assertEqual(start_cfg.cmd.arguments[0], self.arguments[0])
        self.assertEqual(start_cfg.cmd.arguments[1], self.arguments[1])
        self.assertEqual(start_cfg.cmd.arguments[2], self.arguments[2])
        self.assertEqual(start_cfg.cmd.longlife, self.longlife)
        self.assertEqual(start_cfg.cmd.ssh_login.username, self.ssh_login.username)
        self.assertEqual(start_cfg.cmd.ssh_login.password, self.ssh_login.password)


    def test_start_reply(self):
        json_data = { "result"    : True,
                      "taskid"    : 1,
                      "errcode"   : 0,
                      "stdout"    : [],
                      "stderr"    : [],
                      "cwd"       : '/home/dougpuob',
                      "os"        : os_kind().windows,
                      "fwd_ports" : { "qmp" : 1,
                                      "ssh" : 2 } }
        start_r = start_reply(json_data)

        self.assertEqual(start_r.result, True)
        self.assertEqual(start_r.taskid, 1)
        self.assertEqual(start_r.cwd, '/home/dougpuob')
        self.assertEqual(start_r.os, os_kind().windows)
        self.assertEqual(start_r.fwd_ports.qmp, 1)
        self.assertEqual(start_r.fwd_ports.ssh, 2)

    def test_start_request(self):
        start_cmd = start_command(self.program, self.arguments, self.longlife, self.ssh_login)
        start_req = start_request(start_cmd)

        self.assertEqual(start_req.request.command, command_kind().start)
        self.assertEqual(start_req.request.data, start_cmd.toJSON())
        self.assertEqual(json.dumps(start_req.request.data), start_cmd.toTEXT())

    def test_start_response(self):
        json_data = { "result"    : True,
                      "taskid"    : 1,
                      "errcode"   : 0,
                      "stdout"    : [],
                      "stderr"    : [],
                      "cwd"       : '/home/dougpuob',
                      "os"        : os_kind().windows,
                      "fwd_ports" : { "qmp" : 1,
                                      "ssh" : 2 } }

        start_r = start_reply(json_data)
        start_req = start_response(start_r)

        self.assertEqual(start_r.result, True)
        self.assertEqual(start_r.taskid, 1)
        self.assertEqual(start_req.response.command, command_kind().start)
        self.assertEqual(start_req.response.data, json_data)

if __name__ == '__main__':
    unittest.main()
