# -*- coding: utf-8 -*-
import os
import paramiko

from module import config


class SSHClient:
    def __init__(self) -> None:
        self.conn_ssh = None
        self.conn_sftp = None

    def __del__(self):
        pass

    def close(self):
        self.close_sftp()

        if self.conn_ssh:
            self.conn_ssh.close()
            self.conn_ssh = None

    def close_sftp(self):
        if self.conn_sftp:
            self.conn_sftp.close()
            self.conn_sftp = None

    def open_sftp_over_ssh(self, ssh_conn):
        try:
            self.conn_sftp = ssh_conn.open_sftp()
            return self.conn_sftp

        except Exception as e:
            print(e)

        return None

    def open(self, addr:str, port:int, username:str, password:str, enable_sftp:bool=True):
        try:
            self.conn_ssh = paramiko.SSHClient()
            self.conn_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.conn_ssh.connect(addr, port, username, password, banner_timeout=200, timeout=200)

            if enable_sftp:
                self.open_sftp_over_ssh(self.conn_ssh)
                return self.conn_ssh, self.conn_sftp
            else:
                return self.conn_ssh

        except Exception as e:
            print(e)

        return None

    def mkdir_p(self, remote, is_dir=False):

        dirs_ = []
        if is_dir:
            dir_ = remote
        else:
            dir_, basename = os.path.split(remote)
        while len(dir_) > 1:
            dirs_.append(dir_)
            dir_, _  = os.path.split(dir_)

        if len(dir_) == 1 and not dir_.startswith("/"):
            dirs_.append(dir_) # For a remote path like y/x.txt

        while len(dirs_):
            dir_ = dirs_.pop()
            try:
                self.conn_sftp.stat(dir_)
            except:
                self.conn_sftp.mkdir(dir_)


    def cmd_dispatch(self, file_cmd:config.file_command):
        result = False
        stdout = []
        stderr = []
        errcode = 0

        try:
            if file_cmd.kind == "s2g_upload" or file_cmd.kind == "c2g_upload":
                if file_cmd.newdir:
                    self.mkdir_p(file_cmd.newdir, True)
                self.conn_sftp.put(file_cmd.filepath, file_cmd.savepath)
                result = True

            elif file_cmd.kind == "s2g_download" or file_cmd.kind == "c2g_download":
                self.conn_sftp.get(file_cmd.filepath, file_cmd.savepath)
                result = True

            else:
                result = False
                self.stderr = ["Unsupport direction kind !!!"]
                self.errcode = -2


        except Exception as e:
            result = False
            stderr = [str(e)]
            errcode = -1


        reply_data = {
                "taskid"    : file_cmd.taskid,
                "result"    : result,
                "errcode"   : errcode,
                "stderr"    : stderr,
                "stdout"    : stdout,
            }

        return reply_data
