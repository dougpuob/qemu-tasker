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

from inspect import currentframe, getframeinfo
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

    def __init__(self,
                 socket_addr:config.socket_address,
                 pushpool_path:str,
                 taskid:int,
                 start_data:config.start_command_request_data):

        #
        # Definitions
        #
        self.WORKDIR_NAME = "qemu-tasker"

        self.start_data = start_data
        self.socket_addr = socket_addr
        self.longlife = start_data.longlife * 60
        self.taskid = taskid


        #
        # QEMU
        #
        self.qemu_pid    = 0
        self.qemu_thread = None
        self.qemu_proc   = None
        self.qemu_base_args = []


        #
        # Resources
        #
        self.path_obj = OsdpPath()
        self.is_alive = True
        self.is_ready = False
        self.status = config.task_status().waiting
        self.result = config.command_return()

        avail_tcp_ports = self.find_avaliable_ports(taskid, 2)
        self.forward_port = config.forward_port(avail_tcp_ports[0], avail_tcp_ports[1])

        workdir_path = self.path_obj.realpath('.')
        pushdir_name = datetime.now().strftime("%Y%m%d_%H%M%S_") + str(taskid)
        pushpool_path = self.path_obj.realpath(os.path.join(pushpool_path, pushdir_name))
        self.server_info = config.server_environment_information(
                                        workdir_path,
                                        pushpool_path)

        self.guest_info = config.guest_environment_information()


        # SSH
        self.ssh_obj = ssh_link()
        self.qmp_obj = QEMUMonitorProtocol((self.socket_addr.address, self.forward_port.qmp), server=True)
        self.ssh_info = start_data.ssh
        self.flag_is_qmp_connected = False
        self.flag_is_ssh_connected = False


        #
        # QEMU devices flags
        #
        self.attach_qemu_device_nic()
        self.attach_qemu_device_qmp()

        #
        # F
        # .00000000000000000000000000000000000003inal step to launch QEMU.
        #
        self.qemu_thread = threading.Thread(target=self.thread_routine_to_create_proc)
        self.qemu_thread.setDaemon(True)
        self.qemu_thread.start()


    def __del__(self):

        if self.qmp_obj:
            self.qmp_obj.close()

        if self.qemu_proc:
            self.qemu_proc = None


    def wait_to_create(self):
        times = 10
        while times > 0:
            sleep(1)
            if self.qemu_proc and self.qmp_obj:
                return True
            times = times - 1

        return False


    def clear(self):
        self.result.clear()


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


    def send_exec(self, cmd_data:config.exec_command_request_data, is_base64:bool):
        self.clear()

        logging.info("QEMU (taskid={}) send_exec()".format(self.taskid))
        logging.info("QEMU (taskid={}) cmd_data.program={}".format(self.taskid, cmd_data.program))
        logging.info("QEMU (taskid={}) cmd_data.argument={}".format(self.taskid, cmd_data.argument))
        logging.info("QEMU (taskid={}) cmd_data.is_base64={}".format(self.taskid, cmd_data.is_base64))

        if None == self.ssh_obj.tcp_socket:
            return False

        self.status = config.task_status().processing

        cmd_str = cmd_data.program
        arg_str = ""
        if cmd_data.argument:
            if is_base64:
                b64 = base64.b64decode(cmd_data.argument)
                utf8 = b64.decode("utf-8")
                arg_str = utf8
            else:
                arg_str = cmd_data.argument

            cmd_str = cmd_str + " " + arg_str

        logging.info("cmd_str={}".format(cmd_str))

        try:
            cmdret = self.ssh_obj.execute(cmd_str)

            self.result.info_lines.extend(cmdret.info_lines)
            self.result.error_lines.extend(cmdret.error_lines)
            self.result.errcode = cmdret.errcode

            retval = True

        except Exception as e:
            retval = False
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)


        self.status = config.task_status().ready
        return retval


    def send_qmp(self, cmd_data:config.qmp_command_request_data):
        self.clear()

        logging.info("QEMU (taskid={}) send_qmp()".format(self.taskid))
        logging.info("QEMU (taskid={}) cmd_data.execute={}".format(self.taskid, cmd_data.execute))
        logging.info("QEMU (taskid={}) cmd_data.argsjson={}".format(self.taskid, cmd_data.argsjson))
        logging.info("QEMU (taskid={}) cmd_data.is_base64={}".format(self.taskid, cmd_data.is_base64))

        self.status = config.task_status().processing

        argsjson = ""
        if cmd_data.is_base64:
            b64 = base64.b64decode(cmd_data.argsjson)
            utf8 = b64.decode("utf-8")
            argsjson = json.loads(utf8)
        else:
            argsjson = json.loads(cmd_data.argsjson)

        if self.qmp_obj:
            qmsg = self.qmp_obj.cmd(cmd_data.execute, args=argsjson)
            self.result.info_lines.append(qmsg)

        self.status = config.task_status().ready
        return (self.result.errcode == 0)


    def send_push(self, cmd_data:config.push_command_request_data):
        self.clear()

        logging.info("QEMU (taskid={}) send_push()".format(self.taskid))

        self.status = config.task_status().processing

        final_cmdret = config.command_return()
        selected_files = []

        dirlist = os.listdir(self.server_info.pushpool_path)
        for file_from in dirlist:
            fullpath = os.path.join(self.server_info.pushpool_path, file_from)
            fullpath = self.path_obj.normpath_posix(fullpath)

            if os.path.exists(fullpath):
                selected_files.append(fullpath)
            else:
                logging.error("Path not found ({}) !!!".format(fullpath))

        if self.flag_is_ssh_connected:
            for file_from in selected_files:
                basename = os.path.basename(file_from)
                file_to = os.path.join(self.guest_info.pushpool_name, basename)
                file_to = self.path_obj.normpath(file_to)

                cmdret = self.ssh_obj.upload(file_from, file_to)
                self.result.error_lines.extend(cmdret.info_lines)
                self.result.error_lines.extend(cmdret.error_lines)
                self.result.errcode = cmdret.errcode

                if 0 != cmdret.errcode:
                    break

        self.status = config.task_status().ready
        return (final_cmdret.errcode == 0)


    def is_qmp_connected(self):
        return self.flag_is_qmp_connected


    def is_ssh_connected(self):
        return self.flag_is_ssh_connected


    def attach_qemu_device_nic(self):
        arg1 = ["-netdev", "user,id=network0,hostfwd=tcp::{}-:{}".format(self.forward_port.ssh, 22)]
        arg2 = ["-net", "nic,model=e1000,netdev=network0"]
        self.qemu_base_args.extend(arg1)
        self.qemu_base_args.extend(arg2)


    def attach_qemu_device_qmp(self):
        arg1 = ["-chardev", "socket,id=qmp,host={},port={}".format(self.socket_addr.address, self.forward_port.qmp)]
        arg2 = ["-mon", "chardev=qmp,mode=control"]
        self.qemu_base_args.extend(arg1)
        self.qemu_base_args.extend(arg2)


    def thread_routine_to_create_proc(self):
        self.create()

        while self.is_alive:
            sleep(1)
            if self.qemu_proc:
                try:
                    stdout, stderr = self.qemu_proc.communicate()
                    self.result.errcode = self.qemu_proc.returncode

                    if stdout:
                        self.result.info_lines.extend(stdout)

                    if stderr:
                        self.result.error_lines.extend(stderr)

                except Exception as e:
                    frameinfo = getframeinfo(currentframe())
                    errmsg = ("exception={0}".format(e)) + '\n' + \
                             ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                            ("frameinfo.lineno={0}".format(frameinfo.lineno))
                    logging.exception(errmsg)


    def thread_qmp_wait_accept(self):
        logging.info("command.py!qemu_machine::thread_wait_qmp_accept()")
        if self.qmp_obj:
            self.qmp_obj.accept()
            self.flag_is_qmp_connected = True


    def thread_ssh_try_connect(self, host_addr, host_port, username, password):
        logging.info("command.py!qemu_machine::thread_wait_ssh_connect()")
        while (not self.flag_is_ssh_connected) and (None != self.qemu_proc):
            try:
                logging.info("QEMU(taskid={0}) is trying to connect ... (host_addr={1}, host_port={2})".format(self.taskid, host_addr, host_port))
                self.ssh_obj.connect(host_addr, host_port, username, password)
                if self.ssh_obj.tcp_socket and self.ssh_obj.conn_ssh_session:
                    self.flag_is_ssh_connected = True
                    self.status = config.task_status().querying
                    logging.info("QEMU(taskid={0}) self.status={1}".format(self.taskid, self.status))
                    logging.info("QEMU(taskid={0}) is connected.".format(self.taskid))
                    Break

            except ConnectionRefusedError as e:
                logging.warning("SSH connection was refused, is going to retry again !!! (username={} ,password={})".format(username, password))

            except Exception as e:
                frameinfo = getframeinfo(currentframe())
                errmsg = ("exception={0}".format(e)) + '\n' + \
                        ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                        ("frameinfo.lineno={0}".format(frameinfo.lineno))

            sleep(1)


        logging.info("QEMU(taskid={0}) is trying to query information from current guest OS.".format(self.taskid))



        guest_info_os_kind = config.os_kind().unknown
        guest_info_homedir_path =''
        guest_info_pushdir_name =''


        #
        # Detect OS kind by trying the `uname` or `systeminfo` commands.
        # - `uname` for Linux and macOS
        # - `systeminfo` for Windows
        #
        cmdret = self.ssh_obj.execute('uname -a')
        if cmdret.errcode == 0:
            stdout = ''.join(cmdret.info_lines).strip()
            if stdout.find("Linux") > 0:
                guest_info_os_kind = config.os_kind().linux
            if stdout.find("Darwin") > 0:
                guest_info_os_kind = config.os_kind().macos
        else:
            cmdret = self.ssh_obj.execute('systeminfo')
            if cmdret.errcode == 0:
                guest_info_os_kind = config.os_kind().windows

        logging.info("QEMU(taskid={0}) guest_info_os_kind={1}".format(self.taskid, guest_info_os_kind))


        #
        # Get guest current working directory path
        #
        if guest_info_os_kind == config.os_kind().windows:

            # Try cmd.exe
            cmdret = self.ssh_obj.execute('echo %cd%')
            guest_info_homedir_path = ''.join(cmdret.info_lines).strip()

            # Try powershell.exe
            if "%cd%" == guest_info_homedir_path:
                cmdret = self.ssh_obj.execute('(Get-Location).Path')
                guest_info_homedir_path = ''.join(cmdret.info_lines).strip()
            else:
                pass
        else:
            cmdret = self.ssh_obj.execute('pwd')
            guest_info_homedir_path = ''.join(cmdret.info_lines).strip()


        guest_info_workdir_name = os.path.join(self.WORKDIR_NAME)
        logging.info("QEMU(taskid={0}) guest_info_workdir_name ={1}".format(self.taskid, guest_info_workdir_name))

        guest_info_pushdir_name = os.path.join(self.WORKDIR_NAME, "pushpool")
        logging.info("QEMU(taskid={0}) guest_info_pushdir_name ={1}".format(self.taskid, guest_info_pushdir_name))

        guest_info_pushdir_path = self.path_obj.normpath(os.path.join(guest_info_homedir_path, guest_info_pushdir_name))
        logging.info("QEMU(taskid={0}) guest_info_pushdir_path ={1}".format(self.taskid, guest_info_pushdir_path))

        guest_info_workdir_path = self.path_obj.normpath(os.path.join(guest_info_homedir_path, self.WORKDIR_NAME))
        logging.info("QEMU(taskid={0}) guest_info_workdir_path ={1}".format(self.taskid, guest_info_workdir_path))


        # Set working directory.
        self.ssh_obj.apply_os_kind(guest_info_os_kind)
        self.ssh_obj.apply_workdir_name(guest_info_workdir_name)
        self.ssh_obj.apply_pushdir_name(guest_info_pushdir_name)
        self.ssh_obj.apply_workdir_path(guest_info_workdir_path)
        self.ssh_obj.apply_pushdir_path(guest_info_pushdir_path)


        # Create Guest Information.
        # C:\\Users\\dougpuob\\qemu-tasker\\pushpool
        # ^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^ <-- pushdir_name
        #   homedir_path       ^^^^^^^^^^^ <-- workdir_name
        self.guest_info = config.guest_environment_information(
                                        guest_info_os_kind,
                                        guest_info_homedir_path,
                                        guest_info_workdir_path,
                                        guest_info_workdir_name,
                                        guest_info_pushdir_name)


        # Create filepool directory.
        cmdret = self.ssh_obj.mkdir(guest_info_pushdir_name)
        logging.info("QEMU(taskid={0}) create filepool directory ({1})".format(self.taskid, guest_info_pushdir_name))
        logging.info("  cmdret.errcode={0}".format(cmdret.errcode))
        logging.info("  cmdret.info_lines={0}".format(cmdret.info_lines))
        logging.info("  cmdret.error_lines={0}".format(cmdret.error_lines))

        # Append envrionment variable.
        #logging.info("QEMU(taskid={0}) append envirnment variable to PATH".format(self.taskid))
        #self.ssh_obj.append_workdir_to_path()

        # Update path environment variable
        old_envvar_path = self.ssh_obj.get_path_environment_variable()
        if old_envvar_path:
            new_envvar_path = old_envvar_path + guest_info_workdir_path + ";"
            self.ssh_obj.update_path_envvar(new_envvar_path)
        logging.info("QEMU(taskid={0}) new_envvar_path={1}".format(self.taskid, new_envvar_path))

        # Update status of QEMU instance.
        if self.guest_info.os_kind != config.os_kind().unknown:
            self.status = config.task_status().ready
        logging.info("QEMU(taskid={0}) self.status={1}".format(self.taskid, self.status))


    def connect_ssh(self):
        logging.info("Connecting SSH ...")
        if self.flag_is_ssh_connected:
            return

        wait_ssh_thread = threading.Thread(target = self.thread_ssh_try_connect, args=(self.socket_addr.address,
                                                                                       self.forward_port.ssh,
                                                                                       self.start_data.ssh.account.username,
                                                                                       self.start_data.ssh.account.password))
        wait_ssh_thread.setDaemon(True)
        wait_ssh_thread.start()


    def connect_qmp(self):
        logging.info("Connecting QMP ...")
        if self.flag_is_qmp_connected:
            return

        qmp_accept_thread = threading.Thread(target = self.thread_qmp_wait_accept)
        qmp_accept_thread.setDaemon(True)
        qmp_accept_thread.start()


    def create(self):
        self.clear()
        self.status = config.task_status().creating

        qemu_cmdargs = []
        qemu_cmdargs.append(self.start_data.cmd.program)
        qemu_cmdargs.extend(self.start_data.cmd.arguments)
        qemu_cmdargs.extend(self.qemu_base_args)
        logging.info("qemu_cmdargs={}".format(qemu_cmdargs))

        os.makedirs(self.server_info.pushpool_path)

        # Make a QMP server so connect before launching QEMU process.
        self.connect_qmp()

        self.qemu_proc = subprocess.Popen(qemu_cmdargs, shell=False, close_fds=True)
        self.qemu_pid = self.qemu_proc.pid

        self.status = config.task_status().connecting
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

        if self.qmp_obj:
            self.qmp_obj.close()

        # waiting for it to die
        retry = 0
        is_alive = True
        while retry <= 60 and is_alive:
            retry = retry + 1
            is_alive = self.is_proc_alive()
            sleep(1)

        # still alive is a failure case
        if is_alive:
            self.result.errcode = -1
            self.result.info_lines.append("the process still existing (PID is {})".format(self.qemu_pid))
            return False
        else:
            self.result.clear()
            return True

    def decrease_longlife(self):
        self.longlife = self.longlife - 1

