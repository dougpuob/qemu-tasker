# -*- coding: utf-8 -*-
from email import message
import socket
import threading
import time
import logging
import json
import pprint

import psutil
import re
import subprocess

from module import command
from module import config

class server:
    def __init__(self, host_ip, host_port):
        logging.info("socker.py!server::__init__(), Host:%s Port:%d", host_ip, host_port)
        self.socker_server = None

        self.is_started = True
        self.host_info = command.host_information(host_ip, host_port)

        self.task_index = 0
        self.task_base_id = 10000                
        self.qemu_inst_list = []
        self.qemu_inst_list_killing_waiting = []

        # Port
        self.occupied_ports = []

        # Thread objects
        self.thread_task = None 
        self.thread_postpone  = None
        self.thread_tcp = None

    def __del__(self):
        self.is_started = False
        self.socker_server.close()

        self.thread_tcp = None
        self.thread_task = None 
        self.thread_postpone  = None        

    def stop(self):
        self.is_started = False

    def start(self):
        logging.info("socker.py!server::start()")

        # Start QEMU machine.
        self.thread_task = threading.Thread(target = self.thread_routine_longlife_counting)
        self.thread_task.setDaemon(True)
        self.thread_task.start()

        # Start postpone actions.
        self.thread_postpone = threading.Thread(target = self.thread_routine_killing_waiting)
        self.thread_postpone.setDaemon(True)
        self.thread_postpone.start()

        # Start listering of tasker server.
        self.thread_tcp = threading.Thread(target = self.thread_routine_listening_tcp)
        self.thread_tcp.setDaemon(True)
        self.thread_tcp.start()        
        self.thread_tcp.join()

    def get_bool(self, result):
        if result:
            return "True "
        else:
            return "False"

    def thread_routine_longlife_counting(self):	
        logging.info("socker.py!server::thread_routine_longlife_counting()")
        print('thread_routine_longlife_counting ...')

        while self.is_started:
            time.sleep(1)
           
            print('------------------------------------')
            print('QEMU instance number = {}'.format(len(self.qemu_inst_list)))
            index = 0
            for qemu_inst in self.qemu_inst_list:
                index = index + 1
                if qemu_inst.get_task_info().get_longlife() > 0:
                    taskid = qemu_inst.get_task_info().get_taskid()
                    is_qmp_connected = self.get_bool(qemu_inst.is_qmp_connected())
                    is_ssh_connected = self.get_bool(qemu_inst.is_ssh_connected())
                    spare_secs = qemu_inst.task_info.get_longlife()

                    print('  Instance#{} TaskId:{} Ports:{} QMP:{} SSH:{} Longlife:{}(secs)'.format(
                            index, 
                            taskid, 
                            qemu_inst.avail_tcp_ports, 
                            is_qmp_connected, 
                            is_ssh_connected, 
                            spare_secs))

                    qemu_inst.get_task_info().decrease_longlife()                    
                else:
                    self.qemu_inst_list_killing_waiting.append(qemu_inst)
                    self.qemu_inst_list.remove(qemu_inst)
                    
                if not qemu_inst.qemu_proc:
                    self.qemu_inst_list.remove(qemu_inst)

    def thread_routine_killing_waiting(self):	
        logging.info("socker.py!server::thread_routine_postpone_actions()")
        print('thread_routine_postpone_actions ...')
        
        while self.is_started:
            # Handling killing waiting list.
            for qemu_inst in self.qemu_inst_list_killing_waiting:
                
                kill_ret = qemu_inst.kill()
                if kill_ret:
                    self.qemu_inst_list_killing_waiting.remove(qemu_inst)

            time.sleep(1)

    def get_new_taskid(self):        
        logging.info("socker.py!server::get_new_taskid()")        

        self.task_index = self.task_index + 1
        return self.task_base_id + (self.task_index * 10)

    def dispatch_command(self, taskid, cmd):
        ret:bool = False
        out_text = ""
        err_text = ""

        for qemu_inst in self.qemu_inst_list:
            if qemu_inst.task_info.get_taskid() == taskid:
                if cmd.kind == command.command_kind.Exec:
                    ret, msg_lines, err_lines = qemu_inst.exec_ssh_command(cmd)
                elif cmd.kind == command.command_kind.Qmp:
                    ret, out_text, err_text = qemu_inst.exec_qmp_command(cmd)
                elif cmd.kind == command.command_kind.Kill:
                    ret, out_text, err_text = self.exec_terminate_qemu(qemu_inst)
                else:
                    err_text = "TASKID is not FOUND"
                break
        
        return ret, out_text, err_text

    def thread_routine_listening_tcp(self):
        logging.info("socker.py!server::thread_routine_listening_tcp()")
        print('thread_worker_tcp ...')

        self.socker_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socker_server.bind((self.host_info.host_tcp_addr, self.host_info.host_tcp_port))
        self.socker_server.listen(10)

        while True:
            conn, addr = self.socker_server.accept()
            client_mesg = str(conn.recv(1024), encoding='utf-8')
            logging.info("socker.py!server::thread_routine_listening_tcp(), client_mesg=" + client_mesg)
            if client_mesg.startswith("{\"request\":"):
                
                client_cmd = json.loads(client_mesg)
                print(client_cmd)                
                logging.info(client_cmd)

                ret = False
                out_text = ""
                err_text = ""

                if "start" == client_cmd['request']['command']:                    
                    task_cfg = config.start_command_config()

                    taskid:int = self.get_new_taskid()
                    task_cfg.load_config(client_cmd['request']['config'])

                    logging.info("socker.py!server::thread_worker_tcp(), is going to create a new qemu machine ...")
                    qemu_inst = command.qemu_machine(self.host_info, taskid, task_cfg)
                    self.qemu_inst_list.append(qemu_inst)

                    ret = True
                    out_text = ""
                    err_text = ""

                elif "kill" == client_cmd['request']['command']:
                    cmd_cfg = config.kill_command_config()
                    cmd_cfg.load_config(client_cmd['request']['config'])
                    kill_cmd = command.kill_command(cmd_cfg)
                    ret, out_text, err_text = self.dispatch_command(cmd_cfg.taskid, kill_cmd)
                    
                elif "exec" == client_cmd['request']['command']:
                    cmd_cfg = config.exec_command_config()
                    cmd_cfg.load_config(client_cmd['request']['config'])
                    exec_cmd = command.exec_command(cmd_cfg)
                    ret, out_text, err_text = self.dispatch_command(cmd_cfg.taskid, exec_cmd)

                elif "qmp" == client_cmd['request']['command']:
                    cmd_cfg = config.qmp_command_config()
                    cmd_cfg.load_config(client_cmd['request']['config'])
                    qmp_cmd = command.qmp_command(cmd_cfg)
                    ret, out_text, err_text = self.dispatch_command(cmd_cfg.taskid, qmp_cmd)

                else:                    
                    ret = False
                    out_text = "Unsupported command ('{}')".format(client_cmd['request']['command'])
                    err_text = ""

                data = json.dumps(
                        { "response" : {
                            "return" : ret,
                            "stderr" : err_text,
                            "stdout" : out_text
                        }})

                conn.send(bytes(data, encoding="utf-8"))
                conn.close()


class client:
    def __init__(self, host_ip, host_port):
        logging.info("socker.py!client::__init__(), Host:%s Port:%d", host_ip, host_port)
        self.host_ip = host_ip
        self.host_port = host_port
        self.task_info_list_ = []
        self.sock_conn = None

    def __del__(self):
        if self.sock_conn:
            self.sock_conn.close()
            self.sock_conn = None

    def send(self, mesg) -> str:
        logging.info("socker.py!client::send(), Host=%s Port=%d", self.host_ip, self.host_port)        
        print(mesg)

        self.sock_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_conn.connect((self.host_ip, self.host_port))
        
        self.sock_conn.send(mesg.encode())
        
        BUFF_SIZE = 2048
        received = b''
        while True:            
            part = self.sock_conn.recv(BUFF_SIZE)
            received = received + part
            if len(part) < BUFF_SIZE:
                break
                
        self.sock_conn.close()
        return str(received, encoding='utf-8')

    def run_start_cmd(self, start_cmd_cfg):
        logging.info("socker.py!client::run_start_cmd(), Host=%s Port=%d", self.host_ip, self.host_port)        
        start_cmd = command.start_command(start_cmd_cfg)
        mesg = start_cmd.get_json_text()
        received = self.send(mesg)
        print(received)

    def run_kill_cmd(self, kill_cmd_cfg):
        logging.info("socker.py!client::run_kill_cmd(), Host=%s Port=%d", self.host_ip, self.host_port)
        kill_cmd = command.kill_command(kill_cmd_cfg)
        mesg = kill_cmd.get_json_text()        
        received = self.send(mesg)
        print(received)
    
    def run_exec_cmd(self, exec_cmd_cfg):
        logging.info("socker.py!client::run_exec_cmd(), Host=%s Port=%d", self.host_ip, self.host_port)
        exec_cmd = command.exec_command(exec_cmd_cfg)
        mesg = exec_cmd.get_json_text()        
        received = self.send(mesg)
        print(received)

    def run_qmp_cmd(self, qmp_cmd_cfg):
        logging.info("socker.py!client::run_qmp_cmd(), Host=%s Port=%d", self.host_ip, self.host_port)
        exec_cmd = command.qmp_command(qmp_cmd_cfg)
        mesg = exec_cmd.get_json_text()        
        received = self.send(mesg)
        print(received)
