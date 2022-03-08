import unittest
import sys
import os
import json

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
sys.path.insert(0, PROJECT_DIR)

from module.config import command_kind
from module.config import status_config
from module.config import status_command
from module.config import status_reply
from module.config import status_request
from module.config import status_response
from module.config import task_status

class test_status(unittest.TestCase):
    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)

    def test_status_command(self):
        stat_cmd = status_command(10010)

        self.assertEqual(stat_cmd.taskid, 10010)

    def test_status_config(self):
        json_data = { "taskid"   : 10010 }
        stat_cfg = status_config(json_data)

        self.assertEqual(stat_cfg.cmd.toJSON(), json_data)

    def test_status_reply(self):
        json_data = { "result"  : True,
                      "taskid"  : 10010,
                      "errcode" : 0,
                      "stdout"  : [],
                      "stderr"  : [],
                      "status"  : task_status().running,
                      "pid"     : 12345,
                      "fwd_ports" : { "qmp" : 1,
                                      "ssh" : 2 },                      
                      "ssh_info" : { "targetaddr" : "192.168.0.1",
                                     "targetport" : 123,
                                     "username" : "dougpuob",
                                     "password" : "dougpuob" },
                      "filepool" : "filepool",
                      "is_connected_qmp" : True,
                      "is_connected_ssh" : True}

        stat_r = status_reply(json_data)

        self.assertEqual(stat_r.result, True)
        self.assertEqual(stat_r.taskid, 10010)
        self.assertEqual(stat_r.errcode, 0)
        self.assertEqual(stat_r.stdout, [])
        self.assertEqual(stat_r.stderr, [])
        self.assertEqual(stat_r.pid, 12345)
        self.assertEqual(stat_r.status, task_status().running)
        self.assertEqual(stat_r.fwd_ports.qmp, 1)
        self.assertEqual(stat_r.fwd_ports.ssh, 2)
        
        self.assertEqual(stat_r.ssh_info.targetaddr, "192.168.0.1")
        self.assertEqual(stat_r.ssh_info.targetport, 123)
        self.assertEqual(stat_r.ssh_info.username, "dougpuob")
        self.assertEqual(stat_r.ssh_info.password, "dougpuob")
        
        self.assertEqual(stat_r.filepool, "filepool")
        
        self.assertEqual(stat_r.is_connected_qmp, True)
        self.assertEqual(stat_r.is_connected_ssh, True)

    def test_status_request(self):
        stat_cmd = status_command(10010)
        stat_req = status_request(stat_cmd)

        self.assertEqual(stat_req.request.command, command_kind().status)
        self.assertEqual(stat_req.request.data, stat_cmd.toJSON())
        self.assertEqual(json.dumps(stat_req.request.data), stat_cmd.toTEXT())

    def test_status_response(self):
        json_data = { "result"  : True,
                      "taskid"  : 10010,
                      "errcode" : 0,
                      "stdout"  : [],
                      "stderr"  : [],
                      "status"  : task_status().running,
                      "pid"     : 12345,
                      "fwd_ports" : { "qmp" : 1,
                                      "ssh" : 2 },
                      "ssh_info" : { "targetaddr" : "192.168.0.1",
                                     "targetport" : 123,
                                     "username" : "dougpuob",
                                     "password" : "dougpuob" },
                      "filepool" : "filepool",
                      "is_connected_qmp" : True,
                      "is_connected_ssh" : True}

        stat_r = status_reply(json_data)
        stat_req = status_response(stat_r)

        self.assertEqual(stat_req.response.command, command_kind().status)
        self.assertEqual(stat_req.response.data, json_data)

if __name__ == '__main__':
    unittest.main()
