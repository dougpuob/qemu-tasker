# -*- coding: utf-8 -*-
from ast import Raise, Subscript
import os
from re import L
import socket
import logging
import errno

from time import sleep

from module.path import OsdpPath
from module import config
from datetime import datetime


#
# ssh2-python
#
from ssh2.session import Session
from ssh2.sftp import LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR
from ssh2.session import Session
from ssh2.sftp import LIBSSH2_FXF_CREAT, LIBSSH2_FXF_WRITE, \
    LIBSSH2_SFTP_S_IRUSR, LIBSSH2_SFTP_S_IRGRP, LIBSSH2_SFTP_S_IWUSR, \
    LIBSSH2_SFTP_S_IROTH, LIBSSH2_SFTP_S_IXUSR, SFTP, \
    LIBSSH2_SFTP_S_IWUSR, LIBSSH2_SFTP_S_IWGRP, LIBSSH2_SFTP_S_IWOTH, \
    LIBSSH2_SFTP_ATTR_PERMISSIONS


class ssh_link:
    
    
    def __init__(self) -> None:
        self.path = OsdpPath()
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn_sftp = None
        self.conn_ssh_session = None
        self.working_dir = None
        self.os_kind = config.os_kind().unknown

    def set_working_dir(self, working_dir:str):
        self.working_dir = working_dir
        
    def set_os_kind(self, os_kind:config.os_kind):
        self.os_kind = os_kind

    def connect(self, addr:str, port:int, username:str, password:str):
        if self.tcp_socket:
            self.tcp_socket.connect((addr, port))
            self.conn_ssh_session = Session()
            self.conn_ssh_session.handshake(self.tcp_socket)
            self.conn_ssh_session.userauth_password(username, password)
            self.conn_sftp = self.conn_ssh_session.sftp_init()
            self.flag_is_ssh_connected = True
            return True
        return False


    def remote_stat(self, file_path:str):
        if not self.conn_sftp:
            raise ConnectionError()

        file_stat = None
        try:
            file_stat = self.conn_sftp.stat(file_path)
        except Exception as e:
              pass
        finally:
            if file_stat:
                return file_stat
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "remote:" + file_path)


    def execute(self, cmdstr:str):
        cmdret = config.cmd_return()

        if None == self.conn_ssh_session:
            return cmdret

        ssh_chanl = None

        try:
            ssh_chanl = self.conn_ssh_session.open_session()            
            if self.working_dir:
                if self.os_kind == config.os_kind().windows:
                    ssh_chanl.execute("cd {} && {}".format(self.working_dir, cmdstr))
                else:
                    ssh_chanl.execute("cd {} ; {}".format(self.working_dir, cmdstr))
            else:
                ssh_chanl.execute(cmdstr)

            times = 5
            while times > 0:

                sleep(0.5)
                times = times - 1

                size, data = ssh_chanl.read()
                lines = [line.decode('utf-8') for line in data.splitlines()]
                cmdret.info_lines.extend(lines)
                while size > 0:
                    size, data = ssh_chanl.read()
                    lines = [line.decode('utf-8') for line in data.splitlines()]
                    cmdret.info_lines.extend(lines)

                size, data = ssh_chanl.read_stderr()
                lines = [line.decode('utf-8') for line in data.splitlines()]
                cmdret.error_lines.extend(lines)
                while size > 0:
                    size, data = ssh_chanl.read_stderr()
                    cmdret.error_lines.extend(lines)

            cmdret.errcode = ssh_chanl.get_exit_status()

        except Exception as e:
            print(e)
            logging.exception(e)
            cmdret.error_lines.append(str(e))

        finally:
            if ssh_chanl:
                ssh_chanl.close()

        return cmdret

    def realpath(self, path:str):
    
        cmdret = config.cmd_return()

        try:
            cmdret.info_lines.append("raw_path={}".format(path))
            
            real_path = self.conn_sftp.realpath(path)
            cmdret.info_lines.append("real_path={}".format(real_path))
            
            cmdret.errcode = 0

        except Exception as e:
            cmdret.error_lines.append("exception occured at realpath() function !!!")
            cmdret.error_lines.append(("exception={0}".format(e)))
            cmdret.errcode = -1

        finally:
            return cmdret
        
    def stat(self, path:str):
        
        cmdret = config.cmd_return()

        try:
            attrs = self.conn_sftp.stat(path)
            cmdret.info_lines.append("attrs.uid={}".format(attrs.uid))
            cmdret.info_lines.append("attrs.gid={}".format(attrs.gid))
            cmdret.info_lines.append("attrs.permissions={}".format(attrs.permissions))
            cmdret.info_lines.append("attrs.atime={}".format(attrs.atime ))
            cmdret.info_lines.append("attrs.mtime={}".format(attrs.mtime ))
            cmdret.info_lines.append("attrs.flags={}".format(attrs.flags  ))
            cmdret.info_lines.append("attrs.filesize={}".format(attrs.filesize ))
            
            cmdret.errcode = 0

        except Exception as e:
            cmdret.error_lines.append("exception occured at stat() function !!!")
            cmdret.error_lines.append(("exception={0}".format(e)))
            cmdret.errcode = -1

        finally:
            return cmdret


    def exists(self, path:str):

        cmdret = self.realpath(path)
        if cmdret.errcode == 0:
            cmdret_stat = self.stat(path)
            cmdret.errcode = cmdret_stat.errcode
            cmdret.error_lines.extend(cmdret_stat.error_lines)
            cmdret.info_lines.extend(cmdret_stat.info_lines)

        return cmdret


    def readdir(self, subdir:str):

        cmdret = config.cmd_return()

        try:
            splitor = '/'
            homedir = self.conn_sftp.realpath('.')

            expandpath = homedir + splitor + subdir
            readdir = []
            with self.conn_sftp.opendir(expandpath) as fh:
                readdir = list(fh.readdir())

            dir_list = []
            for dir in readdir:
                dir_list.append(dir[1].decode("utf-8"))

            cmdret.errcode = 0
            cmdret.data = dir_list

        except Exception as e:
            errmsg = ("exception={0}".format(e))
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -1

        finally:
            return cmdret


    def mkdir(self, subdir:str):

        mode = LIBSSH2_SFTP_S_IRUSR | \
               LIBSSH2_SFTP_S_IWUSR | \
               LIBSSH2_SFTP_S_IRGRP | \
               LIBSSH2_SFTP_S_IROTH | \
               LIBSSH2_SFTP_S_IXUSR

        cmdret = config.cmd_return()
        if self.path.is_abs(subdir):    
            cmdret.errcode = -1    
            cmdret.error_lines.append('Absolute path is not allowed !!!')
            cmdret.error_lines.append('subdir={}'.format(subdir))
            return cmdret

        try:            
            homedir = self.conn_sftp.realpath('.')
            
            splitor = ''
            path_list = []
            if config.os_kind().windows == self.os_kind:
                path_list.extend(subdir.split('\\'))
                splitor = '\\'
            else:
                path_list.extend(subdir.split('/'))
                splitor = '/'

            expandpath = homedir
            for sub_path in path_list:
                with self.conn_sftp.opendir(expandpath) as fh:
                    readdir = list(fh.readdir())

                    dir_list = []
                    for dir in readdir:
                        dir_list.append(dir[1].decode("utf-8"))

                    expandpath = expandpath + splitor + sub_path
                    found = sub_path in dir_list
                    if not found:
                        self.conn_sftp.mkdir(expandpath, mode)

            cmdret.errcode = 0

        except Exception as e:
            errmsg = ("exception={0}".format(e))
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -1

        finally:
            return cmdret


    def download(self, file_from:str, local_dirpath:str):
        cmdret = config.cmd_return()

        try:
            before = datetime.now()

            cmdret.info_lines.append("from={0}".format(file_from))
            file_from = self.conn_sftp.realpath(file_from)
            if file_from.find(':') > 0 and file_from.startswith('/'):
                file_from = file_from[1:].replace('/', '\\')

            cmdret.info_lines.append("from={0}".format(file_from))
            cmdret.info_lines.append("to={0}".format(local_dirpath))

            file_stat = self.remote_stat(file_from)

            with self.conn_sftp.open(file_from, LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as fh_src, \
                open(local_dirpath, 'wb') as fh_dst:
                for size, data in fh_src:
                    fh_dst.write(data)

            diff = (datetime.now()-before)
            cmdret.info_lines.append("consumed_time={}".format(diff))
            cmdret.errcode = 0

        except Exception as e:
            errmsg = ("exception={0}".format(e))
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -1

        finally:
            return cmdret


    def upload(self, file_from:str, file_to:str):

        cmdret = config.cmd_return()

        mode = LIBSSH2_SFTP_S_IRUSR | \
               LIBSSH2_SFTP_S_IWUSR | \
               LIBSSH2_SFTP_S_IRGRP | \
               LIBSSH2_SFTP_S_IROTH

        f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
        
        if True != os.path.exists(file_from):
            cmdret.errcode = -1
            cmdret.error_lines.append("The specific file is not there !!!")
            cmdret.error_lines.append("file_from={}".format(file_from))
            return cmdret
        
        # cmdret = self.exists(file_to)
        # if cmdret.errcode != 0:
        #     cmdret.error_lines.append("The specific file is not there !!!")
        #     cmdret.error_lines.append("file_to={}".format(file_to))
        #     return cmdret
        
        try:
            before = datetime.now()

            buf_size = 1024 * 1024 * 5
            cmdret.info_lines.append("from={0}".format(file_from))
            cmdret.info_lines.append("to={0}".format(file_to))

            with open(file_from, 'rb', buf_size) as fh_src, \
                self.conn_sftp.open(file_to, f_flags, mode) as fh_dst:
                data = fh_src.read(buf_size)
                while data:
                    fh_dst.write(data)
                    data = fh_src.read(buf_size)

            diff = (datetime.now()-before)
            cmdret.info_lines.append("consumed_time={}".format(diff))
            cmdret.errcode = 0

        except Exception as e:
            errmsg = "exception={0}".format(str(e))
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -1

        finally:
            return cmdret
