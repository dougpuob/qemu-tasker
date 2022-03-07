# -*- coding: utf-8 -*-
from ast import Raise
import os
from re import L
import socket
import logging
import errno

from time import sleep


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
    LIBSSH2_SFTP_S_IROTH
    
    

class ssh_link:
    def __init__(self) -> None:
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        
        self.conn_sftp = None
        self.conn_ssh_session = None

    
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
            print("ssh_chanl={0}".format(ssh_chanl))                
            
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

        finally:
            if ssh_chanl:
                ssh_chanl.close()

        return cmdret

    def download(self, file_from:str, file_to:str):
        cmdret = config.cmd_return()
        
        cmdret.info_lines.append("file_to={0}".format(file_to))
        cmdret.info_lines.append("file_from={0}".format(file_from))
        
        try:
            before = datetime.now()
            
            file_from = self.conn_sftp.realpath(file_from)
            cmdret.info_lines.append("file_from(realpath)={0}".format(file_from))
            if file_from.find(':') > 0 and file_from.startswith('/'):
                file_from = file_from[1:].replace('/', '\\')            
            cmdret.info_lines.append("file_from(normalization)={0}".format(file_from))                        
            file_stat = self.remote_stat(file_from)
            with self.conn_sftp.open(file_from, LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as fh_src, \
                open(file_to, 'wb') as fh_dst:
                for size, data in fh_src:
                    fh_dst.write(data)

            diff = (datetime.now()-before)                
            rate = (file_stat.filesize / 1024000.0) / diff.total_seconds()            
            
            cmdret.info_lines.append("Finished writing remote file in {0}, transfer rate {1} MB/s".format(diff, rate))
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
        
        try:
            before = datetime.now()
            
            buf_size = 1024 * 1024 * 5
            file_stat = None
                        
            file_stat = os.stat(file_from)            
            
            with open(file_from, 'rb', buf_size) as fh_src, \
                self.conn_sftp.open(file_to, f_flags, mode) as fh_dst:
                data = fh_src.read(buf_size)        
                while data:
                    fh_dst.write(data)
                    data = fh_src.read(buf_size)

            diff = (datetime.now()-before)
            rate = (file_stat.st_size / 1024000.0) / diff.total_seconds()
    
            cmdret.info_lines.append("Finished writing remote file in {0}, transfer rate {1} MB/s".format(diff, rate))
            cmdret.errcode = 0
            
        except Exception as e:
            errmsg = "exception={0}".format(str(e))            
            cmdret.error_lines.append(errmsg)
            cmdret.errcode = -1

        finally:
            return cmdret
