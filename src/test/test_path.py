import unittest
import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
sys.path.insert(0, PROJECT_DIR) 

from module.path import OsdpPath

class test_path(unittest.TestCase):
    
    def test_basename(self):
        osdp_path = OsdpPath()
        path_list = [
            'MyFile.txt',
            'C:\\MyFile.txt',
            '/MyFile.txt',
            '/home/dougpuob/MyFile.txt',
            'C:\\home\\dougpuob\\MyFile.txt',
            'C:/home/dougpuob/MyFile.txt'
            ]
        for path in path_list:
            self.assertEqual(osdp_path.basename(path), 'MyFile.txt', "path={}".format(path))
        
        
    def test_normpath_abs(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.normpath('c:/Windows'), 'c:\\Windows')
        self.assertEqual(osdp_path.normpath('c:/A/B/C\D\E'), 'c:\\A\\B\\C\\D\\E')
        self.assertEqual(osdp_path.normpath('c:/A/B/C\.\E'), 'c:\\A\\B\\C\\E')
        self.assertEqual(osdp_path.normpath('c:/A/B/C\..\E'), 'c:\\A\\B\\E')
        self.assertEqual(osdp_path.normpath('c:/A/B/C\..\..\..\E'), 'c:\\E')
        self.assertEqual(osdp_path.normpath('c:/A/B/C\..\.\..\E'), 'c:\\A\\E')
        self.assertEqual(osdp_path.normpath('c:/A/B/C\D\\E'), 'c:\\A\\B\\C\\D\\E')

        
    def test_normpath_windows_abs(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.normpath_windows('c:/Windows'), 'c:\\Windows')
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/C\D\E'), 'c:\\A\\B\\C\\D\\E')
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/C\.\E'), 'c:\\A\\B\\C\\E')
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/C\..\E'), 'c:\\A\\B\\E')
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/C\..\..\..\E'), 'c:\\E')
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/C\..\.\..\E'), 'c:\\A\\E')
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/C\D\\E'), 'c:\\A\\B\\C\\D\\E')


    def test_normpath_windows_rel(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.normpath_windows('A/B/C\D\\E'), 'A\\B\\C\\D\\E')
        self.assertEqual(osdp_path.normpath_windows('A/B/C/..\D\\E'), 'A\\B\\D\\E')
        self.assertEqual(osdp_path.normpath_windows('A/B/C/./..\D\\E'), 'A\\B\\D\\E')
        self.assertEqual(osdp_path.normpath_windows('A/B/C/../..\D\\E'), 'A\\D\\E')
        self.assertEqual(osdp_path.normpath_windows('A/B/C/../..\D\\E'), 'A\\D\\E')
        self.assertEqual(osdp_path.normpath_windows('A/B/C/../../..\D\\E'), 'D\\E')
        
        
    def test_normpath_rel(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.normpath('A/B/C\D\\E'), 'A/B/C/D/E')
        self.assertEqual(osdp_path.normpath('A/B/C/..\D\\E'), 'A/B/D/E')
        self.assertEqual(osdp_path.normpath('A/B/C/./..\D\\E'), 'A/B/D/E')
        self.assertEqual(osdp_path.normpath('A/B/C/../..\D\\E'), 'A/D/E')
        self.assertEqual(osdp_path.normpath('A/B/C/../..\D\\E'), 'A/D/E')
        self.assertEqual(osdp_path.normpath('A/B/C/../../..\D\\E'), 'D/E')


    def test_normpath_windows_special_cases(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.normpath_windows('c:/A/B/..\..\..\..\E'), 'c:\\E')
        self.assertEqual(osdp_path.normpath_windows('A/B/C/../../../..\D\\E'), 'D\\E')


    def test_is_abs(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.is_abs('c:/File.txt'), True)
        self.assertEqual(osdp_path.is_abs('/home/File.txt'), True)
        
        
    def test_is_rel(self):
        osdp_path = OsdpPath()
        self.assertEqual(osdp_path.is_rel('File.txt'), True)
        self.assertEqual(osdp_path.is_rel('home/File.txt'), True)
        
        
if __name__ == '__main__':
    unittest.main()
