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

from inspect import currentframe, getframeinfo

import psutil
import subprocess

import time

from datetime import datetime
from module import config
from module.path import OsdpPath
from module.qmp import QEMUMonitorProtocol
from module.puppet_client import puppet_client
from module.pyrc.rc import inncmd_sysinfo
from module.pyrc.rc import rcresult


class qemu_instance:

    def __init__(self,
                 setting,
                 pushpool_path:str,
                 taskid:int,
                 start_data:config.start_command_request_data):

        #
        # Definitions
        #
        self.WORKDIR_NAME = "qemu-tasker"

        self.setting = setting
        self.start_data = start_data
        self.longlife = start_data.longlife * 60
        self.taskid = taskid


        #
        # QEMU
        #
        self.qemu_pid    = 0
        self.qemu_thread = None
        self.qemu_proc   = None
        self.qemu_base_args = []
        self.qemu_full_cmdargs = []


        #
        # Resources
        #
        self.path_obj = OsdpPath()
        self.is_alive = True
        self.is_ready = False
        self.status = config.task_status().waiting
        self.result = config.command_return()

        avail_tcp_ports = self.find_avaliable_ports(taskid, 3) # QMP,SSH,PUP
        self.forward_port = config.forward_port(avail_tcp_ports[0], # QMP
                                                avail_tcp_ports[1], # SSH
                                                avail_tcp_ports[2], # PUP
                                                )


        self.socket_gov_addr = config.socket_address(self.setting.Governor.Address, self.setting.Governor.Port)
        self.socket_puppet = config.socket_address(self.setting.Puppet.Address, self.forward_port.pup)

        workdir_path = self.path_obj.realpath('.')
        pushdir_name = datetime.now().strftime("%Y%m%d_%H%M%S_") + str(taskid)
        pushpool_path = self.path_obj.realpath(os.path.join(pushpool_path, pushdir_name))
        self.server_info = config.server_environment_information(
                                        self.socket_gov_addr,
                                        workdir_path,
                                        pushpool_path)

        self.guest_info = config.guest_environment_information()

        # Connections status
        self.qmp_obj = QEMUMonitorProtocol((self.socket_gov_addr.address, self.forward_port.qmp), server=True)
        self.pup_obj = puppet_client(config.socket_address(self.setting.Governor.Address, self.forward_port.pup), self.WORKDIR_NAME)
        self.connections_status = config.connections_status()

        #
        # QEMU devices flags
        #
        self.attach_qemu_device_nic()
        self.attach_qemu_device_qmp()

        #
        # Final step to launch QEMU.
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
            time.sleep(1)
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

        logging.info("self.server_info.pushpool_path={0}".format(self.server_info.pushpool_path))
        dirlist = os.listdir(self.server_info.pushpool_path)
        logging.info("dirlist={0}".format(dirlist))
        for filepath in dirlist:
            fullpath = self.path_obj.normpath_posix(os.path.join(self.server_info.pushpool_path, filepath))
            logging.info("fullpath={0}".format(fullpath))

            if os.path.exists(fullpath):
                selected_files.append(fullpath)
            else:
                logging.error("Path not found ({}) !!!".format(fullpath))

        result: rcresult = self.pup_obj.upload(selected_files, 'pushpool')
        self.status = config.task_status().ready

        final_cmdret.errcode = result.errcode
        return (final_cmdret.errcode == 0)


    def is_qmp_connected(self):
        is_connected = (self.connections_status.QMP == config.connection_kind().connected)
        return is_connected


    def is_pup_connected(self):
        return self.pup_obj.is_connected()


    def attach_qemu_device_nic(self):
        ssh_listen_port = 22
        pup_listen_port = self.setting.Puppet.Port.Cmd
        hostfwd_ssh    = "hostfwd=tcp::{}-:{}".format(self.forward_port.ssh, ssh_listen_port)
        hostfwd_pupcmd = "hostfwd=tcp::{}-:{}".format(self.forward_port.pup, pup_listen_port)
        # arg1 = ["-net", "nic,model=e1000"]
        # arg2 = ["-net", "user,{},{}".format(hostfwd_ssh, hostfwd_pupcmd)]
        arg1 = ["-netdev", "user,id=net0,{},{}".format(hostfwd_ssh, hostfwd_pupcmd)]
        arg2 = ["-device", "e1000-82545em,netdev=net0,id=net0"]
        self.qemu_base_args.extend(arg1)
        self.qemu_base_args.extend(arg2)


    def attach_qemu_device_qmp(self):
        gov_host_addr = self.setting.Governor.Address
        arg1 = ["-chardev", "socket,id=qmp,host={},port={}".format(gov_host_addr, self.forward_port.qmp)]
        arg2 = ["-mon", "chardev=qmp,mode=control"]
        self.qemu_base_args.extend(arg1)
        self.qemu_base_args.extend(arg2)


    def thread_routine_to_create_proc(self):
        self.create()

        while self.is_alive:
            time.sleep(1)
            if self.qemu_proc:
                try:
                    stdout, stderr = self.qemu_proc.communicate()
                    self.result.errcode = self.qemu_proc.returncode

                    if stdout:
                        logging.info(stdout)
                        self.result.info_lines.extend(stdout)

                    if stderr:
                        logging.info(stderr)
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
            self.connections_status.QMP = config.connection_kind().connected
            logging.info("QMP is connected.")


    def thread_puppet_try_connect(self, target_addr, target_port):
        logging.info("thread_pup_try_connect()")
        logging.info("thread_pup_try_connect() ({0})".format(self.is_pup_connected()))

        assert self.pup_obj, 'self.pup_obj is None !!!'

        while True:
            try:
                if self.pup_obj.is_connected():
                    logging.info("QEMU(taskid={}) is_connected_to_puppet={}".format(self.taskid, True))
                    self.connections_status.PUP = config.connection_kind().connected
                    self.status = config.task_status().querying
                    break
                else:
                    logging.info("QEMU(taskid={0}) is trying to connect puppet (cmd) ...)".format(self.taskid))
                    ret = self.pup_obj.connect(self.socket_puppet)
                    #logging.info("ret={0}".format(ret))
                    #logging.info("pup_obj.is_cmd_connected={0}".format(self.pup_obj.is_connected()))

            except ConnectionRefusedError as e:
                logging.warning("Failed to establish puppet connection, is going to retry again !!!")

            except Exception as e:
                frameinfo = getframeinfo(currentframe())
                errmsg = ("exception={0}".format(e)) + '\n' + \
                         ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                         ("frameinfo.lineno={0}".format(frameinfo.lineno))
                logging.exception(errmsg)

            finally:
                time.sleep(1)


        #
        # Create filepool directory.
        #
        self.pup_obj.mkdir('pushpool')


        #
        # Query OS information
        #
        logging.info("QEMU(taskid={0}) is trying to query information from current guest OS. (puppet)".format(self.taskid))


        #
        # Detect OS kind by trying the `uname` or `systeminfo` commands.
        # - `uname` for Linux and macOS
        # - `systeminfo` for Windows
        #
        # logging.info('trying to execute `uname` command ...')
        # cmdret = self.pup_obj.execute('uname')
        # logging.info('`uname` (cmdret.errcode={})'.format(cmdret.errcode))

        # guest_info_os_kind = config.os_kind().unknown
        # if cmdret.errcode == 0:
        #     stdout = ''.join(cmdret.info_lines).strip()
        #     if stdout.find("Linux") > 0:
        #         guest_info_os_kind = config.os_kind().linux
        #     if stdout.find("Darwin") > 0:
        #         guest_info_os_kind = config.os_kind().macos
        # else:
        #     logging.info('trying to execute `systeminfo` command ...')
        #     cmdret = self.pup_obj.execute('systeminfo')
        #     logging.info('`systeminfo` (cmdret.errcode={})'.format(cmdret.errcode))
        #     if cmdret.errcode == 0:
        #         guest_info_os_kind = config.os_kind().windows
        pc_info: inncmd_sysinfo = self.pup_obj.get_sysinfo()

        guest_info_os_kind = config.os_kind().unknown
        if pc_info.osname == 'windows':
            guest_info_os_kind = config.os_kind().windows
        elif pc_info.osname == 'darwin':
            guest_info_os_kind = config.os_kind().macos
        elif pc_info.osname == 'linux':
            guest_info_os_kind = config.os_kind().macos
        logging.info("QEMU(taskid={0}) guest_info_os_kind={1}".format(self.taskid, pc_info.osname))


        #
        # Get guest current working directory path
        #
        guest_info_homedir_path = pc_info.homedir
        guest_info_workdir_name = ''
        guest_info_pushdir_name = ''
        guest_info_pushdir_path = ''
        guest_info_workdir_path = ''

        guest_info_workdir_name = os.path.join(self.WORKDIR_NAME)
        logging.info("QEMU(taskid={0}) guest_info_workdir_name ={1}".format(self.taskid, guest_info_workdir_name))

        guest_info_pushdir_name = os.path.join(self.WORKDIR_NAME, "pushpool")
        logging.info("QEMU(taskid={0}) guest_info_pushdir_name ={1}".format(self.taskid, guest_info_pushdir_name))

        guest_info_pushdir_path = self.path_obj.normpath(os.path.join(guest_info_homedir_path, guest_info_pushdir_name))
        logging.info("QEMU(taskid={0}) guest_info_pushdir_path ={1}".format(self.taskid, guest_info_pushdir_path))

        guest_info_workdir_path = self.path_obj.normpath(os.path.join(guest_info_homedir_path, self.WORKDIR_NAME))
        logging.info("QEMU(taskid={0}) guest_info_workdir_path ={1}".format(self.taskid, guest_info_workdir_path))



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



        # cmdret = self.pup_obj.mkdir('qemu-tasker/pushpool')
        # logging.info("QEMU(taskid={0}) create filepool directory ({1})".format(self.taskid, guest_info_pushdir_name))
        # logging.info("  cmdret.errcode={0}".format(cmdret.errcode))
        # logging.info("  cmdret.info_lines={0}".format(cmdret.info_lines))
        # logging.info("  cmdret.error_lines={0}".format(cmdret.error_lines))


        # Update status of QEMU instance.
        if self.guest_info.os_kind != config.os_kind().unknown:
            self.status = config.task_status().ready
        logging.info("QEMU(taskid={0}) self.status={1}".format(self.taskid, self.status))


    def connect_puppet(self):
        logging.info("Connecting Puppet ...")
        if self.is_pup_connected():
            return

        wait_puttet_thread = threading.Thread(target = self.thread_puppet_try_connect,
                                              args=(self.socket_gov_addr.address,
                                                    self.forward_port.pup))
        wait_puttet_thread.setDaemon(True)
        wait_puttet_thread.start()


    def connect_qmp(self):
        logging.info("Connecting QMP ...")
        if self.is_qmp_connected():
            return

        qmp_accept_thread = threading.Thread(target = self.thread_qmp_wait_accept)
        qmp_accept_thread.setDaemon(True)
        qmp_accept_thread.start()


    def create(self):
        self.clear()
        self.status = config.task_status().creating

        self.qemu_full_cmdargs.clear()
        self.qemu_full_cmdargs.append(self.start_data.cmd.program)
        self.qemu_full_cmdargs.extend(self.start_data.cmd.arguments)
        self.qemu_full_cmdargs.extend(self.qemu_base_args)
        logging.info("self.qemu_full_cmdargs={}".format(self.qemu_full_cmdargs))

        os.makedirs(self.server_info.pushpool_path)

        # Make a QMP server so connect before launching QEMU process.
        self.connect_qmp()

        self.qemu_proc = subprocess.Popen(self.qemu_full_cmdargs, shell=False, close_fds=True)
        self.qemu_pid = self.qemu_proc.pid

        self.status = config.task_status().connecting
        self.connect_puppet();


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
            time.sleep(1)

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

