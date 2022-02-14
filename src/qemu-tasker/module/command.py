# -*- coding: utf-8 -*-
from ast import arg
from asyncio.subprocess import PIPE
import json
from socket import timeout
from sys import stdout
import os
from typing import Optional
import paramiko
import threading
import subprocess
import logging

import psutil
import re
import subprocess

from time import sleep

from datetime import datetime
from module import config
from module.qmp import QEMUMonitorProtocol

class _task_status(object):
    def Creating():
        return 1
    def Running():
        return 2
    def Killing():
        return 3
    def Abandoned():
        return 4

TASK_STATUS = _task_status()

class host_information:
    def __init__(self, host_tcp_addr, host_tcp_port):
        self.host_tcp_addr = host_tcp_addr
        self.host_tcp_port = host_tcp_port

    def get_host_addr(self):
        return self.host_tcp_addr
    
    def get_host_port(self):
        return self.host_tcp_port

class task_information:
    def __init__(self, host_info, taskid:int, three_avail_tcp_ports, task_cfg):
        self.host_info = host_info
        self.taskid:int = taskid
        self.task_cfg = task_cfg

        self.host_addr = None
        self.host_port:int = 0
        
        self.proc_instance = None
        self.proc_thread = None
        self.proc_pid:int = 0
        self.proc_args = None

        self.port_mon:int = three_avail_tcp_ports[0]
        self.port_ssh:int = three_avail_tcp_ports[1]
        self.port_nc:int  = three_avail_tcp_ports[2]
        
        self.longlife_max:int = task_cfg.longlife * 60
        self.longlife_spare:int = task_cfg.longlife * 60
        
        self.task_status = None

    def get_taskid(self) -> int:
        return self.taskid

    def get_host_addr(self):
        return self.host_info.get_host_addr()

    def get_nc_port(self):
        return self.port_nc
        
    def get_ssh_port(self):
        return self.port_ssh

    def get_monitor_port(self):
        return self.port_mon

    def get_ssh_username(self):
        return self.task_cfg.ssh.username

    def get_ssh_password(self):
        return self.task_cfg.ssh.password

    def get_pid(self) -> int:
        return self.proc_pid

    def get_status(self):
        return self.task_status
    
    def get_longlife(self):
        return self.longlife_spare

    def decrease_longlife(self):
        self.longlife_spare = self.longlife_spare - 1

    def update_status(self, TASK_STATUS):
        self.task_status = TASK_STATUS

    def update_thread(self, thrd):
        self.proc_thread = thrd

    def update_proc(self, proc):
        self.proc_instance = proc
        self.proc_pid = proc.pid
        self.proc_args = proc.args


class qemu_machine:
    def __init__(self, host_info, taskid:int, task_cfg): 
        self.name = "qemu_instance"
        logging.info("command.py!{}::{}()".format(self.name, "__init__"))

        # qemu device attached
        self.is_qemu_device_attached_qmp = False
        self.is_qemu_device_attached_nic = False

        # qemu base args
        self.base_args = []

        # args
        self.host_info = host_info
        self.task_cfg = task_cfg
        self.avail_tcp_ports = self.find_avaliable_ports(taskid, 3)
        self.tcp_port_qmp = self.avail_tcp_ports[0]
        self.tcp_port_ssh = self.avail_tcp_ports[1]
        self.tcp_port_nc  = self.avail_tcp_ports[2]
        self.task_info = task_information(host_info, taskid, self.avail_tcp_ports, task_cfg)

        # qemu instances
        self.qemu_thread = None
        self.qemu_proc  = None

        self.conn_ssh = None
        self.conn_qmp = None

        # connections flags
        self.flag_is_qmp_connected = False
        self.flag_is_ssh_connected = False

        # feature on/off
        self.attach_qemu_device_nic()
        self.attach_qemu_device_qmp()
        self.create(taskid, task_cfg)

    def __del__(self):
        if self.conn_qmp:
            self.conn_qmp.close()

    def terminate(self):
        self.qemu_proc.kill()

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
    
    def exec_on_guest(self, command):
        cmd_str = command.program
        if command.arguments:
             cmd_str = cmd_str + " " + " ".join(command.arguments)        
        if self.conn_ssh:
            stdin,stdout,stderr = self.conn_ssh.exec_command(command=cmd_str)    
            err_lines = []
            msg_lines = []
            if stderr.readable():
                err_lines.extend(stderr.readlines())
            if stdout.readable():
                msg_lines.extend(stdout.readlines())
            return err_lines, msg_lines
        return

    def exec_qmp_command(self, command):        
        if self.conn_qmp:
            ret = self.conn_qmp.cmd(command.execute, args=command.arguments)
            print(ret)
            return ret            

    def is_qmp_connected(self):
        return self.flag_is_qmp_connected

    def is_ssh_connected(self):
        return self.flag_is_ssh_connected

    def attach_qemu_device_qmp(self):
        if self.is_qemu_device_attached_qmp:
            return
        self.is_qemu_device_attached_qmp = True
        host = self.task_info.get_host_addr()
        port = self.task_info.get_monitor_port()        
        arg1 = ["-chardev", "socket,id=mon,host={},port={}".format(host, port)]
        arg2 = ["-mon", "chardev=mon,mode=control"]
        self.base_args.extend(arg1)
        self.base_args.extend(arg2)

    def attach_qemu_device_nic(self):
        if self.is_qemu_device_attached_nic:
            return            
        self.is_qemu_device_attached_nic = True
        port_ssh = self.task_info.get_ssh_port()        
        port_netcat = self.task_info.get_nc_port()        
        arg1 = ["-netdev", "user,id=network0,hostfwd=tcp::{}-:{}".format(port_ssh, 22)]
        arg2 = ["-net", "nic,model=e1000,netdev=network0"]
        self.base_args.extend(arg1)
        self.base_args.extend(arg2)

    def get_task_info(self):
        return self.task_info

    def thread_open_proc(self, prog_args_list, task_info):
        logging.info("command.py!task::thread_open_proc()")

        self.qemu_proc = subprocess.Popen(prog_args_list, shell=False, close_fds = False)
        task_info.update_proc(self.qemu_proc)

        self.create_qmp_connection()
        self.create_ssh_connection()

        self.qemu_proc.wait()
        self.qemu_proc = None

    def thread_wait_qmp_accept(self):
        logging.info("command.py!task::thread_wait_qmp_accept()")
        if self.conn_qmp:
            self.conn_qmp.accept()
            self.flag_is_qmp_connected = self.conn_qmp.get_sock_fd() != 0        

    def thread_wait_ssh_connect(self, host_addr, host_port, username, password):
        logging.info("command.py!task::thread_wait_ssh_connect()")
        while not self.flag_is_ssh_connected:
            try:   
                self.conn_ssh = paramiko.SSHClient()
                self.conn_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                self.conn_ssh.connect(host_addr, host_port, username, password, banner_timeout=200, timeout=200)
                self.flag_is_ssh_connected = True

                stdin,stdout,stderr = self.conn_ssh.exec_command("ping localhost")
                print(stdout)
                print(stderr)                
        
            except Exception as e:
                logging.exception("e=" + str(e))

            sleep(1)

    def create_ssh_connection(self):
        if self.flag_is_ssh_connected:
            return

        if not self.conn_ssh:
            host_addr = self.task_info.get_host_addr()
            host_port = self.tcp_port_ssh
            username = self.task_info.get_ssh_username()
            password = self.task_info.get_ssh_password()
            logging.info("create_ssh_connection().  host_addr={} host_port={} username={} password={}".format(host_addr, host_port, username, password))
            
            wait_ssh_thread = threading.Thread(target = self.thread_wait_ssh_connect, args=(host_addr, host_port, username, password))
            wait_ssh_thread.setDaemon(True)
            wait_ssh_thread.start()
        
    def create_qmp_connection(self):
        if self.flag_is_qmp_connected:
            return

        host_addr = self.task_info.get_host_addr()
        host_port = self.tcp_port_qmp

        print("create_qmp_connection={}".format((host_addr, host_port)))
        self.conn_qmp = QEMUMonitorProtocol((host_addr, host_port), server=True)
        qmp_accept_thread = threading.Thread(target = self.thread_wait_qmp_accept)
        qmp_accept_thread.setDaemon(True)
        qmp_accept_thread.start()

    def create(self, taskid, task_cfg):
        logging.info("command.py!task::create()")
        
        qemu_cmdargs = []
        qemu_cmdargs.append(task_cfg.qemu.prog)
        qemu_cmdargs.extend(task_cfg.qemu.args)
        qemu_cmdargs.extend(self.base_args)

        print(qemu_cmdargs)
        logging.info("command.py!task::create(), qemu_cmdargs=%s", qemu_cmdargs)

        self.qemu_thread = threading.Thread(target = self.thread_open_proc, args=(qemu_cmdargs, self.task_info))
        self.qemu_thread.setDaemon(True)
        self.qemu_thread.start()
    
        self.task_info.update_thread(self.qemu_thread)
        self.task_info.update_status(TASK_STATUS.Creating)       

    def kill(self) -> bool:        
        logging.info("command.py!task::kill()")        
        for proc in psutil.process_iter():
            if proc.pid == self.qemu_proc.pid:
                os.kill(proc.pid, 9)

        sleep(2)
        for proc in psutil.process_iter():
            if proc.pid == self.qemu_proc.pid:
                print(proc)
                return False
            
        return True

    def exec(self, command) -> int:
        logging.info("command.py!task::exec()")        

    def take_runtime_snapshot(self) -> bool:
        logging.info("command.py!task::take_runtime_snapshot()")

    def revert_runtime_snapshot(self) -> bool:
        logging.info("command.py!task::revert_runtime_snapshot()")

class command_kind:
    @property
    def Unknown(self):
        return "unknown"        
    @property
    def Server(self):
        return "server"
    @property
    def Task(self):
        return "task"
    @property
    def Kill(self):
        return "kill"
    @property
    def Exec(self):
        return "exec"
    @property
    def Qmp(self):
        return "qmp"
    @property
    def Info(self):
        return "info"

class command:
    def __init__(self, name, kind=command_kind.Unknown):
        logging.info("command.py!command::__init__()")
        self.name = name        
        self.cmd_json_data = None
        self.kind = kind

    def get_taskid(self) -> int :
        return self.taskid

    def get_basic_schema(self):
        logging.info("command.py!command::get_basic_schema()")
        return { "request" : { 
                    "command" : self.name ,
                    "timestamp" : "" }}

    def get_json_data(self):
        logging.info("command.py!command::get_json_data()")
        return self.cmd_json_data

    def get_json_text(self):
        logging.info("command.py!command::get_json_text()")
        return self.json_to_text(self.cmd_json_data)
    
    def json_to_text(self, json_data):
        logging.info("command.py!command::json_to_text()")
        return json.dumps(json_data)

    def text_to_json(self, json_text):
        logging.info("command.py!command::text_to_json()")
        return json.load(json_text)

class task_command(command):
    def __init__(self, cmd_cfg):
        logging.info("command.py!task_command::__init__()")
        super().__init__("task", command_kind.Task)
        
        self.cmd_json_data = super(task_command, self).get_basic_schema()
        self.cmd_json_data['request']['config'] = {
                "longlife": cmd_cfg.longlife,
                "qemu": {
                    "prog": cmd_cfg.qemu.prog,
                    "args": cmd_cfg.qemu.args,
                },
                "ssh": {
                    "username": cmd_cfg.ssh.username,
                    "password": cmd_cfg.ssh.password
                }
            }
        
class kill_command(command):
    def __init__(self, cmd_cfg):
        logging.info("command.py!kill_command::__init__()")
        super().__init__("kill", command_kind.Kill)

        self.taskid = cmd_cfg.taskid
        self.cmd_json_data = super(kill_command, self).get_basic_schema()
        self.cmd_json_data['request']['config'] = {
                "taskid": cmd_cfg.taskid
            }

class exec_command(command):
    def __init__(self, cmd_cfg):
        logging.info("command.py!kill_command::__init__()")
        super().__init__("exec", command_kind.Exec)

        self.taskid = cmd_cfg.taskid
        self.program = cmd_cfg.program
        self.arguments = cmd_cfg.arguments

        self.cmd_json_data = super(exec_command, self).get_basic_schema()
        self.cmd_json_data['request']['config'] = {
                "taskid": cmd_cfg.taskid,
                "program" : cmd_cfg.program,
                "arguments" : cmd_cfg.arguments
            }

class qmp_command(command):
    def __init__(self, cmd_cfg):
        logging.info("command.py!qmp_command::__init__()")
        super().__init__("qmp", command_kind.Qmp)

        self.taskid = cmd_cfg.taskid
        self.execute = cmd_cfg.execute
        self.arguments = cmd_cfg.arguments

        self.cmd_json_data = super(qmp_command, self).get_basic_schema()
        self.cmd_json_data['request']['config'] = {
                "taskid": cmd_cfg.taskid,
                "execute" : cmd_cfg.execute,
                "arguments" : cmd_cfg.arguments
            }

class qmp_command_creator():
    def __init__(self):
        pass

    def eject(self, device:str, force:Optional[bool]=False):
        """
        Eject a removable medium.
        
        - force: force ejection (json-bool, optional)
        - device: device name (json-string)
        """
        qmp_cmd_json = { "execute"   : "eject", 
                         "arguments" : { "device": device } }
        return qmp_cmd_json

    def change(self, device:str, target:str, arg:Optional[str] = ""):
        """
        Change a removable medium or VNC configuration.

        - "device": device name (json-string)
        - "target": filename or item (json-string)
        - "arg": additional argument (json-string, optional)
        """
        qmp_cmd_json = { "execute"   : "change", 
                         "arguments" : { "device" : device,
                                         "target" : target,
                                         "arg"    : arg } }
        return qmp_cmd_json

    def screendump(self, filename:str):
        """
        Save screen into PPM image.

        - "filename": file path (json-string)
        """
        qmp_cmd_json = { "execute"   : "screendump", 
                         "arguments" : { "filename": filename } }
        return qmp_cmd_json

    def stop(self):
        """
        Stop the emulator.
        """
        qmp_cmd_json = { "execute"   : "stop" }
        return qmp_cmd_json

    def cont(self):
        """
        Resume emulation.       
        """
        qmp_cmd_json = { "execute"   : "cont" }
        return qmp_cmd_json
        
    def system_wakeup(self):
        """
        Wakeup guest from suspend.
        """
        qmp_cmd_json = { "execute"   : "system_wakeup" }
        return qmp_cmd_json
        
    def system_reset(self):
        """
        Reset the system.        
        """
        qmp_cmd_json = { "execute"   : "system_reset" }
        return qmp_cmd_json
        
    def system_powerdown(self):
        """
        Send system power down event.
        """
        qmp_cmd_json = { "execute"   : "system_powerdown" }
        return qmp_cmd_json
        
    def device_add(self, driver:str, bus: Optional[str], id:str):
        """
        
        """
        qmp_cmd_json = { "execute"   : "device_add", 
                         "arguments" : { "driver": driver,
                                         "bus": bus,
                                         "id" : id } }
        return qmp_cmd_json
        
    def device_del(self, id:str):
        """
        Remove a device.

        - "id": the device's ID or QOM path (json-string)
        """
        qmp_cmd_json = { "execute"   : "device_del", 
                         "arguments" : { "id": id } }
        return qmp_cmd_json
        
    def snapshot_load(self, job_id:str, tag:str, vmstate:str, devices:list):
        """
        Load a VM snapshot

        @job-id: identifier for the newly created job
        @tag: name of the snapshot to load.
        @vmstate: block device node name to load vmstate from
        @devices: list of block device node names to load a snapshot from

        Applications should not assume that the snapshot load is complete
        when this command returns. The job commands / events must be used
        to determine completion and to fetch details of any errors that arise.

        Note that execution of the guest CPUs will be stopped during the
        time it takes to load the snapshot.

        It is strongly recommended that @devices contain all writable
        block device nodes that can have changed since the original
        @snapshot-save command execution.

        Returns: nothing
        """
        qmp_cmd_json = { "execute"   : "snapshot-load", 
                         "arguments" : {} }

        if job_id:
            qmp_cmd_json['arguments']['job-id'] = job_id
        if tag:
            qmp_cmd_json['arguments']['tag'] = tag
        if vmstate:
            qmp_cmd_json['arguments']['vmstate'] = vmstate
        if devices:
            qmp_cmd_json['arguments']['devices'] = devices

        return qmp_cmd_json

    def snapshot_save(self, job_id:str, tag:str, vmstate:str, devices:list):
        """
        Save a VM snapshot

        @job-id: identifier for the newly created job
        @tag: name of the snapshot to create
        @vmstate: block device node name to save vmstate to
        @devices: list of block device node names to save a snapshot to

        Applications should not assume that the snapshot save is complete
        when this command returns. The job commands / events must be used
        to determine completion and to fetch details of any errors that arise.

        Note that execution of the guest CPUs may be stopped during the
        time it takes to save the snapshot. A future version of QEMU
        may ensure CPUs are executing continuously.

        It is strongly recommended that @devices contain all writable
        block device nodes if a consistent snapshot is required.

        If @tag already exists, an error will be reported

        Returns: nothing
        """
        qmp_cmd_json = { "execute"   : "snapshot-save", 
                         "arguments" : {} }

        if job_id:
            qmp_cmd_json['arguments']['job-id'] = job_id
        if tag:
            qmp_cmd_json['arguments']['tag'] = tag
        if vmstate:
            qmp_cmd_json['arguments']['vmstate'] = vmstate
        if devices:
            qmp_cmd_json['arguments']['devices'] = devices

        return qmp_cmd_json
        
    def snapshot_delete(self, job_id:str, tag:str, devices:list):
        """
        Delete a VM snapshot

        @job-id: identifier for the newly created job
        @tag: name of the snapshot to delete.
        @devices: list of block device node names to delete a snapshot from

        Applications should not assume that the snapshot delete is complete
        when this command returns. The job commands / events must be used
        to determine completion and to fetch details of any errors that arise.

        Returns: nothing
        """
        qmp_cmd_json = { "execute"   : "snapshot-save", 
                         "arguments" : {} }

        if job_id:
            qmp_cmd_json['arguments']['job-id'] = job_id
        if tag:
            qmp_cmd_json['arguments']['tag'] = tag
        if devices:
            qmp_cmd_json['arguments']['devices'] = devices

        return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json
        
    # def OOOOOOOOOOOOO(self):
    #     """
        
    #     """
    #     qmp_cmd_json = { "execute"   : "OOOOOOOOOOO", 
    #                      "arguments" : { "OOOOOOOOOOO": OOOOOOOOOOO } }
    #     return qmp_cmd_json