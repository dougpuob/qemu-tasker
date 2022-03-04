# -*- coding: utf-8 -*-
from array import array
from ast import arg
from asyncio.subprocess import PIPE
import json
from socket import timeout
from sys import stderr, stdout
import os
import paramiko
import threading
import subprocess
import logging
import socket

from ssh2.session import Session

import psutil
import subprocess

from time import sleep

from datetime import datetime
from module import config
from module.sshclient import SSHClient
from module.qmp import QEMUMonitorProtocol


class qemu_instance:
    def __init__(self, socket_addr:config.socket_address, taskid:int, start_cmd:config.start_command):

        # Resource definition
        self.BUFF_SIZE = 2048
        self.is_alive = True
        self.is_ready = False
        self.guest_os_cwd = None
        self.guest_os_kind = config.os_kind().unknown

        # qemu base args
        self.base_args = []

        # args
        self.start_cmd = start_cmd
        self.socket_addr = socket_addr

        avail_tcp_ports = self.find_avaliable_ports(taskid, 2)
        self.fwd_ports = config.tcp_fwd_ports(avail_tcp_ports[0], avail_tcp_ports[1])

        # qemu
        self.qemu_thread = None
        self.qemu_proc  = None
        self.stderr = []
        self.stdout = []
        self.pid = 0
        self.errcode = 0
        self.status = config.task_status().waiting
        self.longlife = start_cmd.longlife * 60
        self.taskid = taskid

        # SSH
        self.conn_ssh = None
        self.conn_ssh_section = None
        
        # QMP
        self.conn_qmp = None    # QEMU Machine Protocol (QMP)

        #
        # QEMU connection flags
        #
        self.flag_is_qmp_connected = False
        self.flag_is_ssh_connected = False

        #
        # QEMU devices flags
        #
        self.is_qemu_device_attached_nic = False
        self.is_qemu_device_attached_qmp = False
        self.attach_qemu_device_nic()
        self.attach_qemu_device_qmp()

        # final step to launch QEMU.
        self.qemu_thread = threading.Thread(target=self.thread_routine_to_create_proc)
        self.qemu_thread.setDaemon(True)
        self.qemu_thread.start()

    def __del__(self):
        if self.conn_qmp:
            self.conn_qmp.close()

    def wait_to_create(self):
        times = 10
        while times > 0:
            sleep(1)
            if self.qemu_proc and self.conn_qmp:
                return True
            times = times - 1

        return False

    def clear(self):
        self.stderr.clear()
        self.stdout.clear()
        self.errcode = 0

    def find_avaliable_ports(self, start_port, amount):
        occupied_ports = self.get_occupied_ports()

        ret_list = []
        next_start_port = start_port

        index = 0
        while index < amount:
            while True:
                next_start_port = next_start_port + 1
                if not next_start_port in occupied_ports:
                    ret_list.append(next_start_port)
                    occupied_ports.append(next_start_port)
                    break
            index = index + 1
        return ret_list

    def get_occupied_ports(self):
        conns_list = psutil.net_connections()
        ret_ports = []

        for conn in conns_list:
            ret_ports.append(conn.laddr.port)

        return ret_ports

    def send_exec(self, exec_arg:config.exec_argument):
        self.clear()
        
        if None == self.conn_ssh:
            return False

        cmd_str = exec_arg.program
        if exec_arg.argument:
             cmd_str = cmd_str + " " + exec_arg.argument
        
        logging.info("● cmd_str={}".format(cmd_str))                

        try:
            ssh2help = ssh2_helper(self.conn_ssh_section)            
            cmdret = ssh2help.execute(cmd_str)
            
            self.stdout.extend(cmdret.info_lines)
            self.stderr.extend(cmdret.error_lines)
            self.errcode = cmdret.errcode
        
            retval = True
 
        except Exception as e:
            retval = False
            
            print("e=" + str(e))
            logging.exception("e=" + str(e))

        return retval

    def send_qmp(self, qmp_cmd:config.qmp_command):
        self.clear()
        if self.conn_qmp:
            return self.conn_qmp.cmd(qmp_cmd.execute, args=qmp_cmd.argsjson)
        return ""

    def send_file(self, file_cmd:config.file_command):
        self.clear()

        print("● send_file")
        print("file_cmd.taskid={}".format(file_cmd.taskid))
        print("file_cmd.kind={}".format(file_cmd.kind))
        print("file_cmd.filepath={}".format(file_cmd.filepath))
        print("file_cmd.savepath={}".format(file_cmd.savepath))
        print("file_cmd.newdir={}".format(file_cmd.newdir))

        logging.info("● send_file")
        logging.info("file_cmd={}".format(file_cmd.toJSON()))
        logging.info("file_cmd.taskid={}".format(file_cmd.taskid))
        logging.info("file_cmd.kind={}".format(file_cmd.kind))
        logging.info("file_cmd.filepath={}".format(file_cmd.filepath))
        logging.info("file_cmd.savepath={}".format(file_cmd.savepath))
        logging.info("file_cmd.newdir={}".format(file_cmd.newdir))

        print("config.direction_kind.s2g_upload={}".format(config.direction_kind.s2g_upload))
        print("config.direction_kind.s2g_download={}".format(config.direction_kind.s2g_download))

        sshclient = SSHClient()
        sftp = sshclient.open_sftp_over_ssh(self.conn_ssh)

        file_reply_json = sshclient.cmd_dispatch(file_cmd)
        self.errcode = file_reply_json["errcode"]
        self.stderr  = file_reply_json["stderr"]
        self.stdout  = file_reply_json["stdout"]
        sftp.close()

        result  = file_reply_json["result"]
        return result

    def is_qmp_connected(self):
        return self.flag_is_qmp_connected

    def is_ssh_connected(self):
        return self.flag_is_ssh_connected

    def attach_qemu_device_nic(self):
        if self.is_qemu_device_attached_nic:
            return
        self.is_qemu_device_attached_nic = True
        arg1 = ["-netdev", "user,id=network0,hostfwd=tcp::{}-:{}".format(self.fwd_ports.ssh, 22)]
        arg2 = ["-net", "nic,model=e1000,netdev=network0"]
        self.base_args.extend(arg1)
        self.base_args.extend(arg2)

    def attach_qemu_device_qmp(self):
        if self.is_qemu_device_attached_qmp:
            return
        self.is_qemu_device_attached_qmp = True
        arg1 = ["-chardev", "socket,id=qmp,host={},port={}".format(self.socket_addr.addr, self.fwd_ports.qmp)]
        arg2 = ["-mon", "chardev=qmp,mode=control"]
        self.base_args.extend(arg1)
        self.base_args.extend(arg2)

    def thread_routine_to_create_proc(self):
        self.create()

        while self.is_alive:
            sleep(1)
            if self.qemu_proc:
                try:
                    stdout, stderr = self.qemu_proc.communicate()
                    self.errcode = self.qemu_proc.returncode

                    if stdout:
                        self.stdout.extend(stdout)

                    if stderr:
                        self.stderr.extend(stderr)

                except Exception as e:
                    print("{}● exception={}".format(e))
                    logging.info("{}● exception={}".format(e))

    def thread_qmp_wait_accept(self):
        logging.info("command.py!qemu_machine::thread_wait_qmp_accept()")
        if self.conn_qmp:
            self.conn_qmp.accept()
            self.flag_is_qmp_connected = True

    def thread_ssh_try_connect(self, host_addr, host_port, username, password):
        logging.info("command.py!qemu_machine::thread_wait_ssh_connect()")
        while not self.flag_is_ssh_connected:
            try:
                
                #
                # ssh2-python
                #   
                self.conn_ssh = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if self.conn_ssh:
                    self.conn_ssh.connect((host_addr, host_port))
                    self.conn_ssh_section = Session()
                    self.conn_ssh_section.handshake(self.conn_ssh)
                    self.conn_ssh_section.userauth_password(username, password)            
                
                print("self.conn_ssh={0}".format(self.conn_ssh))        
                print("self.conn_ssh_section={0}".format(self.conn_ssh_section))    
                
                #
                # paramiko
                #   
                # self.conn_ssh = paramiko.SSHClient()
                # self.conn_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                # self.conn_ssh.connect(host_addr, host_port, username, password, banner_timeout=200, timeout=200)
                

                self.flag_is_ssh_connected = True
                self.status = config.task_status().running
                break

            except Exception as e:
                logging.exception("e=" + str(e))

            sleep(1)


        stdout_lines = []
        stderr_lines = []
        
        
        ssh2help = ssh2_helper(self.conn_ssh_section)
        
        
        #
        # Detect OS kind by trying the `uname` or `systeminfo` commands.
        # - `uname` for Linux and macOS
        # - `systeminfo` for Windows
        #        
        cmdret = ssh2help.execute('uname -a')
        if cmdret.errcode == 0:
            stdout = ''.join(cmdret.info_lines).strip()
            if stdout.find("Linux") > 0:
                self.guest_os_kind = config.os_kind().linux
            if stdout.find("Darwin") > 0:
                self.guest_os_kind = config.os_kind().macos
        else:
            cmdret = ssh2help.execute('systeminfo')
            if cmdret.errcode == 0:
                self.guest_os_kind = config.os_kind().windows

        #
        # Get guest current working directory path        
        #
        if self.guest_os_kind == config.os_kind().windows:
            cmdret = ssh2help.execute('echo %cd%')
            self.guest_os_cwd = ''.join(cmdret.info_lines).strip()
        else:
            cmdret = ssh2help.execute('pwd')
            self.guest_os_cwd = ''.join(cmdret.info_lines).strip()            

        print("{}● os_kind={}".format("  ", self.guest_os_kind))
        print("{}● cwd={}".format("  ", self.guest_os_cwd))

        logging.info("{}● os_kind={}".format("  ", self.guest_os_kind))
        logging.info("{}● cwd={}".format("  ", self.guest_os_cwd))


    def connect_ssh(self):
        if self.flag_is_ssh_connected:
            return

        if not self.conn_ssh:
            wait_ssh_thread = threading.Thread(target = self.thread_ssh_try_connect, args=(self.socket_addr.addr,
                                                                                           self.fwd_ports.ssh,
                                                                                           self.start_cmd.ssh_login.username,
                                                                                           self.start_cmd.ssh_login.password))
            wait_ssh_thread.setDaemon(True)
            wait_ssh_thread.start()

    def connect_qmp(self):
        if self.flag_is_qmp_connected:
            return

        self.conn_qmp = QEMUMonitorProtocol((self.socket_addr.addr, self.fwd_ports.qmp), server=True)
        qmp_accept_thread = threading.Thread(target = self.thread_qmp_wait_accept)
        qmp_accept_thread.setDaemon(True)
        qmp_accept_thread.start()

    def create(self):
        self.clear()
        self.status = config.task_status().creating

        qemu_cmdargs = []
        qemu_cmdargs.append(self.start_cmd.program)
        qemu_cmdargs.extend(self.start_cmd.arguments)
        qemu_cmdargs.extend(self.base_args)
        logging.info("{}● qemu_cmdargs={}".format("  ", qemu_cmdargs))

        # Make a QMP server so connect before launching QEMU process.
        if self.is_qemu_device_attached_qmp:
            self.connect_qmp()

        self.qemu_proc = subprocess.Popen(qemu_cmdargs, shell=False, close_fds=True)
        self.pid = self.qemu_proc.pid

        self.status = config.task_status().connecting
        if self.is_qemu_device_attached_nic:
            self.connect_ssh()

    def is_proc_alive(self) -> bool:
        if self.qemu_proc:
            for proc in psutil.process_iter():
                if proc.pid == self.qemu_proc.pid:
                    return True
        return False

    def kill(self) -> bool:
        self.clear()

        if None == self.qemu_proc:
            return True

        # first kill by its function.
        self.qemu_proc.kill()

        if self.conn_qmp:
            self.conn_qmp.close()

        if self.conn_ssh:
            self.conn_ssh.close()

        # waiting for it to die
        retry = 0
        is_alive = True
        while retry <= 60 and is_alive:
            retry = retry + 1
            is_alive = self.is_proc_alive()
            sleep(1)

        self.stdout.append("Wait the process around {} seconds (PID is {})".format(retry, self.pid))

        # still alive is a failure case
        if is_alive:
            self.errcode = -1
            self.stderr.append("the process still existing (PID is {})".format(self.pid))
            return False

        return True

    def decrease_longlife(self):
        self.longlife = self.longlife - 1

class cmd_return:
    def __init__(self):
        self.error_lines = []
        self.info_lines = []
        self.errcode = -9999
        
class ssh2_helper:
    def __init__(self, ssh_section):
        self.ssh2_section = ssh_section
    
    
    # if len(stdout_text) >= 2048*100 or len(stderr_text) >= 2048*100:
    #     stderr_text = stderr_text + "\r\nOver maximum line number !!!"
    # retval = False
    # break
    
    def execute(self, cmdstr:str):
        cmdret = cmd_return()        
        
        if None == self.ssh2_section:
            return cmdret
        
        ssh_chanl = None
        
        try:
            ssh_chanl = self.ssh2_section.open_session()
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