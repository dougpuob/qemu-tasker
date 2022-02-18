import unittest
import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
sys.path.insert(0, PROJECT_DIR) 

from module.config import server_config
from module.config import server_config_default


class test_server_config(unittest.TestCase):
    def test_ctor(self):
        json_data = {
            "socket_address": {
                "addr": "localhost",
                "port": 12801
            },
            "qemu_longlife": {
                "instance_maximum": 10,
                "longlife_minutes": 10
            },
            "ssh_login": {
                "username": "dougpuob",
                "password": "dougpuob"
            }
        }
        
        srv_cfg = server_config(json_data)        
        self.assertEqual(srv_cfg.toJSON(), json_data)


class test_server_config_default(unittest.TestCase):
    def test_ctor(self):
        json_data = {
            "socket_address": {
                "addr": "localhost",
                "port": 12801
            },
            "qemu_longlife": {
                "instance_maximum": 10,
                "longlife_minutes": 10
            },
            "ssh_login": {
                "username": "dougpuob",
                "password": "dougpuob"
            }
        }
        
        srv_cfg = server_config_default()        
        self.assertEqual(srv_cfg.toJSON(), json_data)
        
if __name__ == '__main__':
    unittest.main()
