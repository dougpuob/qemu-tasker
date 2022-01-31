# -*- coding: utf-8 -*-
from ast import arg
from asyncio.subprocess import PIPE
import json
from socket import timeout
from sys import stdout
import os
import paramiko
import threading
import subprocess
import logging
from time import sleep
import psutil


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
    def __init__(self, host_info, taskid, task_cfg):
        self.host_info = host_info
        self.taskid = taskid
        self.task_cfg = task_cfg

        self.host_addr = None
        self.host_port = 0
        
        self.proc_instance = None
        self.proc_thread = None
        self.proc_pid = 0
        self.proc_args = None

        self.port_mon = taskid + 1
        self.port_ssh = taskid + 2        
        self.port_nc  = taskid + 3
        
        self.longlife_max = task_cfg.longlife * 60
        self.longlife_spare = task_cfg.longlife * 60
        
        self.task_status = None
        

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


class task_instance:
    def __init__(self, host_info, taskid, task_cfg): 
        logging.info("command.py!task::__init__()")
        self.name_ = ""

        # qemu device attached
        self.is_qemu_device_attached_qmp = False
        self.is_qemu_device_attached_nic = False

        # qemu base args
        self.base_args = []

        # args
        self.host_info = host_info
        self.task_cfg = task_cfg
        self.task_info = task_information(host_info, taskid, task_cfg)        

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

        self.qemu_proc.wait()
        
    def create_ssh_connection(self):
        if self.flag_is_ssh_connected:
            return

        if not self.conn_ssh:
            host_addr = self.task_info.get_host_addr()
            host_port = self.task_info.get_ssh_port()
            username = self.task_info.get_ssh_username()
            password = self.task_info.get_ssh_password()
            logging.info("create_ssh_connection().  host_addr={} host_port={} username={} password={}".format(host_addr, host_port, username, password))

            try:    
                self.conn_ssh = paramiko.SSHClient()
                self.conn_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                                
                self.conn_ssh.connect(host_addr, host_port, username, password, banner_timeout=200)
                self.flag_is_ssh_connected = True

                stdin,stdout,stderr = self.conn_ssh.exec_command("ping localhost")
                print(stdout)
                print(stderr)                
        
            except Exception as e:
                logging.exception("e=" + str(e))
        
    def create_qmp_connection(self):
        if self.flag_is_qmp_connected:
            return

        host_addr = self.task_info.get_host_addr()
        host_port = self.task_info.get_monitor_port()
        print((host_addr, host_port))
        self.conn_qmp = QEMUMonitorProtocol((host_addr, host_port), server=True)        
        self.conn_qmp.accept()
        self.flag_is_qmp_connected = self.conn_qmp.get_sock_fd() != 0

    def exec_ssh(self, command):
        stdin, stdout, stderr = self.conn_ssh.exec_command(command)
        print(stderr)
        print(stdout)

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
                print ("is_running=%d", proc.is_running())
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


class command:
    def __init__(self, name):
        logging.info("command.py!command::__init__()")
        self.name_ = name
        self.jsoncmd = None
    
    def get_basic_schema(self):
        logging.info("command.py!command::get_basic_schema()")
        return { "request" : { 
                    "command" : self.name_ ,
                    "timestamp" : "" }}

    def get_jsoncmd(self):
        logging.info("command.py!command::get_jsoncmd()")
        return self.jsoncmd

    def get_jsoncmd_str(self):
        logging.info("command.py!command::get_jsoncmd_str()")
        return self.json_to_str(self.jsoncmd)
    
    def json_to_str(self, jsoncmd):
        logging.info("command.py!command::json_to_str()")
        return json.dumps(jsoncmd)

    def str_to_json(self, jsoncmd_str):
        logging.info("command.py!command::str_to_json()")
        return json.load(jsoncmd_str)

class task_command(command):
    def __init__(self, task_cfg):
        logging.info("command.py!task_command::__init__()")
        super().__init__("task")
        self.jsoncmd = super(task_command, self).get_basic_schema()
        self.jsoncmd['request']['config'] = {
                "longlife": task_cfg.longlife,
                "qemu": {
                    "prog": task_cfg.qemu.prog,
                    "args": task_cfg.qemu.args,
                },
                "ssh": {
                    "username": task_cfg.ssh.username,
                    "password": task_cfg.ssh.password
                }
            }
        