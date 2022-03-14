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

    def test_qmp_no_arg(self):
        sys.argv = ['qemu-tasker.py',
                    'qmp',
                    '--taskid', '10010',
                    '--execute', 'human-monitor-command']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "qmp")
        self.assertEqual(args.execute, "human-monitor-command")

    def test_qmp_argsjson1(self):
        sys.argv = ['qemu-tasker.py',
                    'qmp',
                    '--taskid', '10010',
                    '--execute', 'human-monitor-command',
                    '--argsjson', '{"command-line" : "info version" }']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "qmp")
        self.assertEqual(args.execute, "human-monitor-command")
        self.assertEqual(args.argsjson, '{"command-line" : "info version" }')

    def test_qmp_argsjson2(self):
        argsjson = {"command-line" : "info version" }
        sys.argv = ['qemu-tasker.py',
                    'qmp',
                    '--taskid', '10010',
                    '--execute', 'human-monitor-command',
                    '--argsjson', json.dumps(argsjson)]

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "qmp")
        self.assertEqual(args.execute, "human-monitor-command")
        self.assertEqual(args.argsjson, json.dumps(argsjson))


if __name__ == '__main__':
    unittest.main()
