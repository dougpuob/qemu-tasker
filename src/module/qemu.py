# -*- coding: utf-8 -*-
from array import array
from ast import Break, arg
from asyncio.subprocess import PIPE
import json
from socket import timeout
from sys import stderr, stdout
import os
import base64
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
from module.sshclient import ssh_link
from module.path import OsdpPath
from module.qmp import QEMUMonitorProtocol


class qemu_instance:
    def __init__(self, socket_addr:config.socket_address, taskid:int, start_cmd:config.start_command):

        self.path = OsdpPath()

        # Resource definition
        self.BUFF_SIZE = 2048
        self.is_alive = True
        self.is_ready = False
        self.workdir_name = "qemu-tasker"
        self.guest_os_cwd_raw = None
        self.guest_os_kind = config.os_kind().unknown
        self.guest_os_work_dir = "qemu-tasker"
        self.guest_os_pushpool_dir = None

        self.pushdir_name = datetime.now().strftime("%Y%m%d_%H%M%S_") + str(taskid)
        self.host_pushdir_path = self.path.realpath(os.path.join("pushpool", self.pushdir_name))

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
        self.ssh_link = ssh_link()

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

    # def normpath(self, path:str):
    #     new_path = None
    #     if self.guest_os_kind == config.os_kind().windows:
    #         new_path = path.replace('/', '\\')
    #     elif self.guest_os_kind == config.os_kind().linux or \
    #          self.guest_os_kind == config.os_kind().macos:
    #         new_path = path.replace('\\', '/')
    #     else:
    #         new_path = path
    #     return new_path

    # def normpath_unix(self, path:str):
    #     return path.replace('\\', '/')

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

    def send_exec(self, exec_arg:config.exec_argument, is_base64:bool):
        self.clear()

        if None == self.ssh_link.tcp_socket:
            return False

        self.status = config.task_status().processing

        cmd_str = exec_arg.program
        arg_str = ""
        if exec_arg.argument:
            if is_base64:
                b64 = base64.b64decode(exec_arg.argument)
                utf8 = b64.decode("utf-8")
                arg_str = utf8
            else:
                arg_str = exec_arg.argument

            #cmd_str = cmd_str + " \"" + arg_str + "\""
            cmd_str = cmd_str + " " + arg_str

        logging.info("arg_base64={}".format(is_base64))
        logging.info("cmd_str={}".format(cmd_str))

        try:
            cmdret = self.ssh_link.execute(cmd_str)

            self.stdout.extend(cmdret.info_lines)
            self.stderr.extend(cmdret.error_lines)
            self.errcode = cmdret.errcode

            retval = True

        except Exception as e:
            retval = False
            logging.exception("exception={}".format(str(e)))


        self.status = config.task_status().ready
        return retval

    def send_qmp(self, qmp_cmd:config.qmp_command):
        self.clear()
        self.status = config.task_status().processing

        final_cmdret = config.cmd_return()
        final_cmdret.errcode = 0

        argsjson = ""
        if qmp_cmd.is_base64:
            b64 = base64.b64decode(qmp_cmd.argsjson)
            utf8 = b64.decode("utf-8")
            argsjson = json.loads(utf8)
        else:
            argsjson = json.loads(qmp_cmd.argsjson)

        if self.conn_qmp:
            return self.conn_qmp.cmd(qmp_cmd.execute, args=argsjson)

        self.status = config.task_status().ready
        return final_cmdret


    def send_push(self, push_cmd:config.push_command):
        self.clear()
        self.status = config.task_status().processing

        final_cmdret = config.cmd_return()
        selected_files = []

        dirlist = os.listdir(self.host_pushdir_path)
        for file_from in dirlist:
            fullpath = os.path.join(self.host_pushdir_path, file_from)
            fullpath = self.path.normpath_posix(fullpath)

            if os.path.exists(fullpath):
                selected_files.append(fullpath)
            else:
                logging.error("Path not found ({}) !!!".format(fullpath))

        if self.flag_is_ssh_connected:
            for file_from in selected_files:
                basename = os.path.basename(file_from)
                file_to = os.path.join(self.guest_os_pushpool_dir, basename)
                file_to = self.path.normpath(file_to)

                cmdret = self.ssh_link.upload(file_from, file_to)
                final_cmdret.info_lines.extend(cmdret.info_lines)
                final_cmdret.error_lines.extend(cmdret.error_lines)
                final_cmdret.errcode = cmdret.errcode
                if 0 != cmdret.errcode:
                    break

        self.status = config.task_status().ready
        return final_cmdret


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
                    logging.exception("exception={}".format(e))

    def thread_qmp_wait_accept(self):
        logging.info("command.py!qemu_machine::thread_wait_qmp_accept()")
        if self.conn_qmp:
            self.conn_qmp.accept()
            self.flag_is_qmp_connected = True

    def thread_ssh_try_connect(self, host_addr, host_port, username, password):
        logging.info("command.py!qemu_machine::thread_wait_ssh_connect()")
        while not self.flag_is_ssh_connected:
            try:
                self.ssh_link.connect(host_addr, host_port,username,password)
                if self.ssh_link.tcp_socket and self.ssh_link.conn_ssh_session:
                    self.flag_is_ssh_connected = True
                    self.status = config.task_status().querying
                    Break

            except Exception as e:
                logging.exception("exceptione={}".format(str(e)))

            sleep(1)

        #
        # Detect OS kind by trying the `uname` or `systeminfo` commands.
        # - `uname` for Linux and macOS
        # - `systeminfo` for Windows
        #
        cmdret = self.ssh_link.execute('uname -a')
        if cmdret.errcode == 0:
            stdout = ''.join(cmdret.info_lines).strip()
            if stdout.find("Linux") > 0:
                self.guest_os_kind = config.os_kind().linux
            if stdout.find("Darwin") > 0:
                self.guest_os_kind = config.os_kind().macos
        else:
            cmdret = self.ssh_link.execute('systeminfo')
            if cmdret.errcode == 0:
                self.guest_os_kind = config.os_kind().windows

        #
        # Get guest current working directory path
        #
        if self.guest_os_kind == config.os_kind().windows:

            # Try cmd.exe
            cmdret = self.ssh_link.execute('echo %cd%')
            self.guest_os_cwd_raw = ''.join(cmdret.info_lines).strip()

            # Try powershell.exe
            if "%cd%" == self.guest_os_cwd_raw:
                cmdret = self.ssh_link.execute('(Get-Location).Path')
                self.guest_os_cwd_raw = ''.join(cmdret.info_lines).strip()
            else:
                pass
        else:
            cmdret = self.ssh_link.execute('pwd')
            self.guest_os_cwd_raw = ''.join(cmdret.info_lines).strip()


        # Set working directory.
        self.guest_os_pushpool_dir = self.path.normpath(os.path.join(self.guest_os_work_dir, "pushpool"), self.guest_os_kind)
        self.ssh_link.set_working_dir(self.guest_os_work_dir)
        self.ssh_link.set_os_kind(self.guest_os_kind)
        logging.info("self.guest_os_pushpool_dir={}".format(self.guest_os_pushpool_dir))


        # Create filepool directory.
        cmdret = self.ssh_link.mkdir(self.guest_os_pushpool_dir)


        if self.guest_os_kind != config.os_kind().unknown:
            self.status = config.task_status().ready


        logging.info("os_kind={}".format(self.guest_os_kind))
        logging.info("cwd={}".format(self.guest_os_work_dir))

        logging.info("os_kind={}".format(self.guest_os_kind))
        logging.info("cwd={}".format(self.guest_os_work_dir))


    def connect_ssh(self):
        if self.flag_is_ssh_connected:
            return

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
        logging.info("qemu_cmdargs={}".format(qemu_cmdargs))

        os.makedirs(self.host_pushdir_path)

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
        self.status = config.task_status().killing

        if None == self.qemu_proc:
            return True

        # first kill by its function.
        self.qemu_proc.kill()

        if self.conn_qmp:
            self.conn_qmp.close()

        # waiting for it to die
        retry = 0
        is_alive = True
        while retry <= 60 and is_alive:
            retry = retry + 1
            is_alive = self.is_proc_alive()
            sleep(1)

        # still alive is a failure case
        if is_alive:
            self.errcode = -1
            self.stderr.append("the process still existing (PID is {})".format(self.pid))
            return False
        else:
            self.errcode = 0
            return True

    def decrease_longlife(self):
        self.longlife = self.longlife - 1
