# -*- coding: utf-8 -*-
from ctypes.wintypes import CHAR
import os
import platform

from module import config

class OsdpPath():


    def __init__(self) -> None:
        pass


    def remove_dot_path(self, path:str, is_root:bool, os_sep:str):
        path_list = path.split(os_sep)
        idx = 0
        while idx < len(path_list):
            if path_list[idx] == '.':
                path_list.pop(idx)
                idx = idx - 1
            elif path_list[idx] == '..':
                if idx > 0:
                    path_list.pop(idx)
                    if is_root and idx == 1:
                        continue
                    path_list.pop(idx-1)
                    idx = idx - 2
                else:
                    path_list.pop(idx)
            idx = idx + 1
        return os_sep.join(path_list)


    def basename(self, path:str) -> str:
        fslash = path.rfind('/')
        bslash = path.rfind('\\')
        pos = max(fslash, bslash)
        if pos >= 0:
            return path[pos+1:]
        else:
            return path


    def normpath(self, path:str, os_kind=None) -> str:
        if os_kind != None:
            if os_kind == config.os_kind().windows:
                return self.normpath_windows(path)
            else:
                return self.normpath_posix(path)

        is_root_win = (path.find(':') >= 0)
        is_root_unix = path.startswith('/')

        os_sep = ''
        new_path = ''
        if is_root_win:
            new_path = path.replace('/', '\\')
            os_sep = '\\'
        elif is_root_unix:
            new_path = path.replace('\\', '/')
            os_sep = '/'
        else:
            fslash_c = 0
            bslash_c = 0
            arr = list(path)
            for c in arr:
                if c == '/':
                    fslash_c = fslash_c + 1
                elif c == '\\':
                    bslash_c = bslash_c + 1
                else:
                    pass
            if fslash_c >= bslash_c:
                os_sep = '/'
                new_path=path.replace('\\', os_sep)
            else:
                os_sep = '\\'
                new_path=path.replace('/', os_sep)

        is_root = is_root_win or is_root_unix
        new_path = self.remove_dot_path(new_path, is_root, os_sep)
        return new_path


    def is_abs(self, path:str) -> bool:
        is_root_win = (path.find(':') !=  -1)
        is_root_unix = path.startswith('/')
        return is_root_win or is_root_unix


    def is_rel(self, path:str) -> bool:
        return not self.is_abs(path)


    def normpath_posix(self, path:str) -> str:
        new_path = path.replace('\\', '/')
        is_root = (new_path.find('/') !=  -1)
        new_path = self.remove_dot_path(new_path, is_root, '\\')
        return new_path


    def normpath_windows(self, path:str) -> str:
        new_path = path.replace('/', '\\')
        is_root = (new_path.find(':') !=  -1)
        new_path = self.remove_dot_path(new_path, is_root, '\\')
        return new_path


    def realpath(self, path:str) -> str:
        new_path = os.path.realpath(path)
        new_path = self.normpath(new_path)
        return new_path


    def realpath_windows(self, path:str) -> str:
        new_path = os.path.realpath(path)
        return self.normpath_windows(new_path)


    def realpath_posix(self, path:str) -> str:
        new_path = os.path.realpath(path)
        return self.normpath_posix(new_path)


    def relpath(self, path1:str, path2:str) -> str:
        path1 = self.realpath(path1)
        path2 = self.realpath(path2)
        short = ''
        long = ''
        ret = ''
        if len(path1) > len(path2):
            short = path2
            long = path1
            ret = long.replace(short, '')
        elif len(path1) < len(path2):
            short = path1
            long = path2
            ret = long.replace(short, '')
        else:
            pass

        return ret
