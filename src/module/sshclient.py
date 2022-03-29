# -*- coding: utf-8 -*-
from ast import Assert, Raise, Subscript
import os
from re import L
import socket
import logging
import errno

from time import sleep
from inspect import currentframe, getframeinfo

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

        self.envvar_path = None

        self.workdir_name = None
        self.pushdir_name = None

        self.workdir_path = None
        self.pushdir_path = None

        self.os_kind = config.os_kind().unknown

    def __del__(self):
        self.tcp_socket.close()

    def apply_pushdir_name(self, pushdir_name:str):
        self.pushdir_name = pushdir_name

    def apply_workdir_name(self, workdir_name:str):
        self.workdir_name = workdir_name

    def apply_pushdir_path(self, pushdir_path:str):
        self.pushdir_path = pushdir_path

    def apply_workdir_path(self, workdir_path:str):
        self.workdir_path = workdir_path


    def apply_os_kind(self, os_kind:config.os_kind):
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


    def get_path_environment_variable(self):

        path_env = ''
        ssh_chanl = self.conn_ssh_session.open_session()
        if ssh_chanl:
            if self.os_kind == config.os_kind().windows:
                ssh_chanl.execute("powershell -C (Get-Item Env:PATH)[0].Value")
            else:
                Assert (config.os_kind().unknown)

            ssh_chanl.wait_eof()

            size, data = ssh_chanl.read()
            logging.info("size={}".format(size))
            logging.info("data={}".format(data))
            text = data.decode('utf-8')
            while size > 0:
                size, data = ssh_chanl.read()
                text = text + data.decode('utf-8')

            ssh_chanl.close()
            path_env = text.strip()

        return  path_env


    def update_path_envvar(self, new_path_value:str):
        self.envvar_path = new_path_value


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
        cmdret = config.command_return()

        if None == self.conn_ssh_session:
            return cmdret

        ssh_chanl = None

        logging.info("Trying to execute command. (cmdstr={})".format(cmdstr))

        try:
            ssh_chanl = self.conn_ssh_session.open_session()
            if None == ssh_chanl:
                errtext = "Failed to call self.conn_ssh_session.open_session() function, because it returned A None object !!!"
                raise ModuleNotFoundError(errtext)

            # # Call setenv() function
            # if self.envvar_path:
            #     ret_setenv = ssh_chanl.setenv("PATH", self.envvar_path)
            #     logging.info("return ssh_chanl.setenv() function. (ret_setenv={})".format(ret_setenv))


            new_cmdstr = cmdstr
            if self.workdir_path:
                if self.os_kind == config.os_kind().windows:
                    new_cmdstr = "cd {} & {}".format(self.workdir_path, cmdstr)
                else:
                    new_cmdstr = "cd {} ; {}".format(self.workdir_path, cmdstr)
            ssh_chanl.execute(new_cmdstr)

            logging.info("Trying to call ssh_chanl.read() function.")
            size, data = ssh_chanl.read()
            logging.info("size={}".format(size))
            logging.info("data={}".format(data))
            lines = [line.decode('utf-8') for line in data.splitlines()]
            cmdret.info_lines.extend(lines)
            while size > 0:
                size, data = ssh_chanl.read()
                lines = [line.decode('utf-8') for line in data.splitlines()]
                cmdret.info_lines.extend(lines)

            logging.info("Trying to call ssh_chanl.read_stderr() function.")
            size, data = ssh_chanl.read_stderr()
            logging.info("size={}".format(size))
            logging.info("data={}".format(data))
            lines = [line.decode('utf-8') for line in data.splitlines()]
            cmdret.error_lines.extend(lines)
            while size > 0:
                size, data = ssh_chanl.read_stderr()
                cmdret.error_lines.extend(lines)

            logging.info("Trying to call ssh_chanl.close() function.")
            ssh_chanl.close()

            logging.info("Trying to call ssh_chanl.wait_closed() function.")
            ret_wait_eof = ssh_chanl.wait_eof()
            logging.info("ssh_chanl.wait_eof() function (ret_wait_eof={})".format(ret_wait_eof))

            logging.info("Trying to call ssh_chanl.get_exit_status() function.")
            cmdret.errcode = ssh_chanl.get_exit_status()
            infotext = "ssh_chanl.get_exit_status() function (cmdret.errcode={})".format(cmdret.errcode)
            logging.info(infotext)

        except ModuleNotFoundError as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -10

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            if ssh_chanl:
                ssh_chanl.close()
            return cmdret


    def realpath(self, path:str):

        cmdret = config.command_return()

        try:
            cmdret.info_lines.append("raw_path={}".format(path))

            real_path = self.conn_sftp.realpath(path)
            cmdret.info_lines.append("real_path={}".format(real_path))

            cmdret.errcode = 0

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append("exception occured at realpath() function !!!")
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            return cmdret

    def stat(self, path:str):

        cmdret = config.command_return()

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
            errmsg = "exception occured at stat() function !!!"
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            return cmdret


    def exists(self, path:str):
        logging.info("path={}".format(path))
        cmdret = self.realpath(path)
        logging.info("cmdret.errcode={}".format(cmdret.errcode))
        logging.info("cmdret.info_lines={}".format(cmdret.info_lines))
        logging.info("cmdret.error_lines={}".format(cmdret.error_lines))
        if cmdret.errcode == 0:
            cmdret_stat = self.stat(path)

            logging.info("cmdret_stat.errcode={}".format(cmdret_stat.errcode))
            logging.info("cmdret_stat.info_lines={}".format(cmdret_stat.info_lines))
            logging.info("cmdret_stat.error_lines={}".format(cmdret_stat.error_lines))

            cmdret.errcode = cmdret_stat.errcode
            cmdret.error_lines.extend(cmdret_stat.error_lines)
            cmdret.info_lines.extend(cmdret_stat.info_lines)

        return cmdret


    def readdir(self, subdir:str):

        cmdret = config.command_return()

        try:
            homedir = self.conn_sftp.realpath('.')
            expandpath = self.path.normpath_posix(os.path.join(homedir, subdir))
            cmdret.info_lines.append("expandpath={}".format(expandpath))

            readdir = []
            logging.info('trying to call the self.conn_sftp.opendir() function. (expandpath={})'.format(expandpath))
            with self.conn_sftp.opendir(expandpath) as fh:
                readdir = list(fh.readdir())

            dir_list = []
            for dir in readdir:
                dir_list.append(dir[1].decode("utf-8"))

            cmdret.errcode = 0
            cmdret.data = dir_list

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = "Exception occured at readdir() function !!! \n" + \
                     ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            return cmdret


    def mkdir(self, subdir:str):
        subdir = self.path.normpath(subdir, self.os_kind)

        mode = LIBSSH2_SFTP_S_IRUSR | \
               LIBSSH2_SFTP_S_IWUSR | \
               LIBSSH2_SFTP_S_IRGRP | \
               LIBSSH2_SFTP_S_IROTH | \
               LIBSSH2_SFTP_S_IXUSR

        cmdret = config.command_return()
        if self.path.is_abs(subdir):
            cmdret.errcode = -1
            cmdret.error_lines.append('absolute path is not allowed !!! subdir={}'.format(subdir))
            return cmdret

        try:
            homedir = self.conn_sftp.realpath('.')

            splitor = ''
            path_list = []
            if config.os_kind().windows == self.os_kind:
                path_list.extend(subdir.split('\\'))
            else:
                path_list.extend(subdir.split('/'))

            expandpath = homedir
            for sub_path in path_list:
                with self.conn_sftp.opendir(expandpath) as fh:
                    readdir = list(fh.readdir())

                    dir_list = []
                    for dir in readdir:
                        dir_list.append(dir[1].decode("utf-8"))

                    # ssh2-python library accept posix path only.
                    #   - /C:/Users/dougpuob/qemu-tasker <-- OK
                    #   - \C:\Users\dougpuob\qemu-tasker <-- Failed
                    expandpath = self.path.normpath_posix(os.path.join(expandpath, sub_path))
                    cmdret.info_lines.append("expandpath={}".format(expandpath))
                    found = sub_path in dir_list
                    if not found:
                        self.conn_sftp.mkdir(expandpath, mode)

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = "Exception occured at mkdir() function !!! \n" + \
                     ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            return cmdret


    def download(self, file_from:str, dstdir:str):
        cmdret = config.command_return()

        try:
            before = datetime.now()

            file_from = self.conn_sftp.realpath(file_from)
            if file_from.find(':') > 0 and file_from.startswith('/'):
                file_from = file_from[1:].replace('/', '\\')

            file_stat = self.remote_stat(file_from)

            with self.conn_sftp.open(file_from, LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as fh_src, \
                open(dstdir, 'wb') as fh_dst:
                for size, data in fh_src:
                    fh_dst.write(data)

            diff = (datetime.now()-before)
            cmdret.info_lines.append("consumed_time={}".format(diff))
            cmdret.errcode = 0

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            return cmdret


    def upload(self, file_from:str, file_to:str):

        cmdret = config.command_return()

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
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -12345

        finally:
            return cmdret
