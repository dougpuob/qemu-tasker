# -*- coding: utf-8 -*-
from array import array
from ast import arg
from asyncio.subprocess import PIPE
import json
from socket import timeout
from sys import stderr, stdout
import os
from typing import Optional
import paramiko
import threading
import subprocess
import logging
import socket

import psutil
import subprocess

from time import sleep

from datetime import datetime
from module import config
from module.qmp import QEMUMonitorProtocol


class qemu_instance:
    def __init__(self, socket_addr:config.socket_address, taskid:int, start_cmd:config.start_command):         
        
        # Resource definition
        self.BUFF_SIZE = 2048
        
        # qemu base args
        self.base_args = []

        # args
        self.start_cmd = None
        self.socket_addr = socket_addr
        
        avail_tcp_ports = self.find_avaliable_ports(taskid, 2)
        self.fwd_ports = config.tcp_fwd_ports(avail_tcp_ports[0], avail_tcp_ports[1]) 

        # qemu
        self.qemu_thread = None
        self.qemu_proc  = None
        self.stderr = None
        self.stdout = None
        self.errcode = 0
        self.status = config.task_status().unknown
        self.longlife = start_cmd.longlife * 60
        self.taskid = taskid

        self.conn_ssh = None
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
        self.create(taskid, start_cmd)

    def __del__(self):
        if self.conn_qmp:
            self.conn_qmp.close()

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
    
    def send_exec(self, exec_args:config.exec_arguments):

        cmd_str = exec_args.program
        if exec_args.arguments:
             cmd_str = cmd_str + " " + " ".join(exec_args.arguments)
        
        print("{}● cmd_str={}".format("  ", cmd_str))
        if self.conn_ssh:
            stdin, stdout, stderr = self.conn_ssh.exec_command(command=cmd_str)
            if stderr.readable():
                lines:array = stderr.readlines()                
                for idx, val in enumerate(lines):
                    lines[idx] = val.replace('\r', '').replace('\n', '')
                self.stderr = lines

            if stdout.readable():
                lines = stdout.readlines()
                for idx, val in enumerate(lines):
                    lines[idx] = val.replace('\r', '').replace('\n', '')
                self.stdout = lines

            return True
            
        return False

    def send_qmp(self, qmp_cmd:config.qmp_command):
        if self.conn_qmp:
            return self.conn_qmp.cmd(qmp_cmd.execute, args=json.loads(qmp_cmd.argsjson))            
        return ""

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

    def thread_qemu_wait_proc(self, qemu_cmdargs):        
        if self.qemu_proc:
            self.qemu_proc.wait()
        
        self.errcode = self.qemu_proc.returncode
        self.stdout, self.stderr = self.qemu_proc.communicate()
        
        self.qemu_proc = None

    def thread_qmp_wait_accept(self):
        logging.info("command.py!qemu_machine::thread_wait_qmp_accept()")
        if self.conn_qmp:
            self.conn_qmp.accept()
            self.flag_is_qmp_connected = True

    def thread_ssh_try_connect(self, host_addr, host_port, username, password):
        logging.info("command.py!qemu_machine::thread_wait_ssh_connect()")
        while not self.flag_is_ssh_connected:
            try:   
                self.conn_ssh = paramiko.SSHClient()
                self.conn_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                self.conn_ssh.connect(host_addr, host_port, username, password, banner_timeout=200, timeout=200)
                self.flag_is_ssh_connected = True
                self.status = config.task_status().running
        
            except Exception as e:
                logging.exception("e=" + str(e))

            sleep(1)

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

    def create(self, taskid, start_cmd:config.start_command):        
        qemu_cmdargs = []
        qemu_cmdargs.append(start_cmd.program)
        qemu_cmdargs.extend(start_cmd.arguments)
        qemu_cmdargs.extend(self.base_args)
        print("{}● qemu_cmdargs={}".format("  ", qemu_cmdargs))

        self.start_cmd = start_cmd
        
        if self.is_qemu_device_attached_qmp:
            self.connect_qmp()

        self.qemu_proc = subprocess.Popen(qemu_cmdargs, shell=False, close_fds=True)                
        
        try:
            self.stdout, self.stderr = self.qemu_proc.communicate(timeout=3)
        except Exception as e:            
                pass
        finally:
            self.errcode = self.qemu_proc.returncode
            if None == self.errcode:
                self.errcode = 0                

        if self.errcode == 0:
            self.qemu_thread = threading.Thread(target=self.thread_qemu_wait_proc, args=(qemu_cmdargs,))
            self.qemu_thread.setDaemon(True)
            self.qemu_thread.start()
            
            self.status = config.task_status().creating

            if self.is_qemu_device_attached_nic:
                self.connect_ssh()
        
        self.status = config.task_status().connecting

    def kill(self) -> bool:        
        if None == self.qemu_proc:
            return True

        # first kill by its function.
        self.qemu_proc.kill()

        # kill by signal if pid found.
        for proc in psutil.process_iter():
            if proc.pid == self.qemu_proc.pid:
                os.kill(proc.pid, 9)
        
        # confirm result
        for proc in psutil.process_iter():
            if proc.pid == self.qemu_proc.pid:
                return False

        return True

    def decrease_longlife(self):
        self.longlife = self.longlife - 1 

