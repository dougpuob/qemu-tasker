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

    def test_exec_no_arg(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010', 
                    '--program', 'ping']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")        
        self.assertEqual(args.program, "ping")
        self.assertEqual(args.argument, None)

    def test_exec_arg(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010', 
                    '--program', 'ping',
                    '--argument', 'a b']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")
        self.assertEqual(args.program, "ping")                
        self.assertEqual(args.argument, "a b")
        
    def test_exec_arg_with_path_windows_1(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010', 
                    '--program', 'ping',
                    '--argument', 'C:\Windows\System32\calc.exe']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")
        self.assertEqual(args.program, "ping")                
        self.assertEqual(args.argument, "C:\Windows\System32\calc.exe")

    def test_exec_arg_with_path_windows_2(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010', 
                    '--program', 'ping',
                    '--argument', 'C:\Program Files (x86)\Internet Explorer\iexplore.exe']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")
        self.assertEqual(args.program, "ping")                
        self.assertEqual(args.argument, "C:\Program Files (x86)\Internet Explorer\iexplore.exe")
        
    def test_exec_arg_with_path_windows_3(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010', 
                    '--program', 'ping',
                    '--argument', 'C://Windows//System32//calc.exe']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")
        self.assertEqual(args.program, "ping")                
        self.assertEqual(args.argument, "C://Windows//System32//calc.exe")
        
    def test_exec_arg_with_path_linux(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010', 
                    '--program', 'ping',
                    '--argument',"/home/dougpuob/clac.out"]

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")
        self.assertEqual(args.program, "ping")                
        self.assertEqual(args.argument, "/home/dougpuob/clac.out")
        
    def test_exec_choco_install_vcredist140(self):       
        sys.argv = ['qemu-tasker.py', 
                    'exec', 
                    '--taskid', '10010',
                    '--program', 'choco',
                    '--argument', 'install -y vcredist140']

        args = cmdargs().get_parsed_args()

        self.assertEqual(args.taskid, 10010)
        self.assertEqual(args.command, "exec")
        self.assertEqual(args.program, "choco")                
        self.assertEqual(args.argument, 'install -y vcredist140')
        
        
if __name__ == '__main__':
    unittest.main()
