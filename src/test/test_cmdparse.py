import unittest
import sys
import os
import sys
import json

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
sys.path.insert(0, PROJECT_DIR) 

from module.cmdparse import cmdargs

class test_cmdparse(unittest.TestCase):
    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)        

    def test_cmdparse_no_args(self):       
        sys.argv = ['qemu-tasker.sys', 
                    'qmp', 
                    '--taskid', '10010', 
                    '--execute', 'human-monitor-command']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "qmp")
        self.assertEqual(args.execute, "human-monitor-command")

    def test_cmdparse_device_add(self):       
        sys.argv = ['qemu-tasker.sys', 
                    'qmp', 
                    '--taskid', '10010', 
                    '--execute', 'human-monitor-command', 
                    '--argsjson', '''{"command-line" : "device_add usb-winusb,id=winusb-01,pcap=winusb-01.pcap" }''']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "qmp")
        self.assertEqual(args.execute, "human-monitor-command")
        self.assertEqual(json.loads(args.argsjson), {"command-line" : "device_add usb-winusb,id=winusb-01,pcap=winusb-01.pcap" })
        
        
if __name__ == '__main__':
    unittest.main()
