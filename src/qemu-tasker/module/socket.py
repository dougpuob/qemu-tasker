# -*- coding: utf-8 -*-
import socket
import threading
import time
import logging
import json
import pprint

from module import command
from module import config

class server:
    def __init__(self, host_ip, host_port):
        logging.info("socker.py!server::__init__(), Host:%s Port:%d", host_ip, host_port)
        self.socker_server = None

        self.is_started = True
        self.host_info = command.host_information(host_ip, host_port)
        self.host_ip = self.host_info.get_host_addr()
        self.host_port = self.host_info.get_host_port()
        self.index_ = 0
        self.taskid_ = 10000        
        self.task_inst_list = []
        self.killing_waiting_list = []

        # Thread objects
        self.thread_task = None 
        self.thread_postpone  = None
        self.thread_tcp = None

    def __del__(self):
        self.is_started = False
        self.socker_server.close()

        self.thread_task = None 
        self.thread_postpone  = None
        self.thread_tcp = None

    def stop(self):
        self.is_started = False

    def start(self):
        logging.info("socker.py!server::start()")

        # Start QEMU machine tasker.
        self.thread_task = threading.Thread(target = self.thread_routine_longlife_counting)
        self.thread_task.setDaemon(True)
        self.thread_task.start()

        # Start postpone actions.
        self.thread_postpone = threading.Thread(target = self.thread_routine_postpone_actions)
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
            print('QEMU instance number = {}'.format(len(self.task_inst_list)))
            index = 0
            for task_inst in self.task_inst_list:
                index = index + 1
                if task_inst.get_task_info().get_longlife() > 0:
                    spare_secs = task_inst.task_info.get_longlife()
                    is_qmp_connected = self.get_bool(task_inst.is_qmp_connected())
                    is_ssh_connected = self.get_bool(task_inst.is_ssh_connected())
                    print('  Instance#{} QMP: {} SSH: {} Longlife: {}(secs)'.format(index, is_qmp_connected, is_ssh_connected, spare_secs))
                    task_inst.get_task_info().decrease_longlife()                    
                else:
                    self.killing_waiting_list.append(task_inst)
                    self.task_inst_list.remove(task_inst)
                    
    def thread_routine_postpone_actions(self):	
        logging.info("socker.py!server::thread_routine_postpone_actions()")
        print('thread_routine_postpone_actions ...')
        
        while self.is_started:

            # Handling postone actions.
            for task_inst in self.task_inst_list:
                # Creating QMP connection
                if not task_inst.is_qmp_connected():
                    task_inst.create_qmp_connection()

                # Creating SSH connection
                if not task_inst.is_ssh_connected():
                    task_inst.create_ssh_connection()

            # Handling killing waiting list.
            for task_inst in self.killing_waiting_list:                
                kill_ret = task_inst.kill()
                if kill_ret:
                    self.killing_waiting_list.remove(task_inst)

            time.sleep(1)

    def get_new_taskid(self):
        logging.info("socker.py!server::get_new_taskid()")
        self.index_ = self.index_ + 1
        self.taskid_ = self.taskid_ + (self.index_ * 10)
        return self.taskid_

    def thread_routine_listening_tcp(self):
        logging.info("socker.py!server::thread_routine_listening_tcp()")
        print('thread_worker_tcp ...')

        self.socker_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socker_server.bind((self.host_ip, self.host_port))
        self.socker_server.listen(10)

        while True:
            conn, addr = self.socker_server.accept()
            client_mesg = str(conn.recv(1024), encoding='utf-8')
            logging.info("socker.py!server::thread_routine_listening_tcp(), client_mesg=" + client_mesg)
            if client_mesg.startswith("{\"request\":"):
                client_cmd = json.loads(client_mesg)
                print(client_cmd)
                logging.info(client_cmd)
                if "task" == client_cmd['request']['command']:
                    taskid = self.get_new_taskid()
                    task_cfg = config.task_config()
                    task_cfg.load_config(client_cmd['request']['config'])

                    logging.info("socker.py!server::thread_worker_tcp(), is going to create a new task ...")
                    task_inst = command.task_instance(self.host_info, taskid, task_cfg)
                    self.task_inst_list.append(task_inst)

                conn.close()

class client:
    def __init__(self, host_ip, host_port):
        logging.info("socker.py!client::__init__(), Host:%s Port:%d", host_ip, host_port)
        self.host_ip = host_ip
        self.host_port = host_port
        self.task_info_list_ = []
        self.command = command.command("")

    def create_task(self, task_cfg):
        logging.info("socker.py!client::create_task(), Host=%s Port=%d", self.host_ip, self.host_port)
        
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((self.host_ip, self.host_port))

        create_task_jsoncmd = command.task_command(task_cfg).get_jsoncmd()
        client_to_server_message = self.command.json_to_str(create_task_jsoncmd)
        client.send(client_to_server_message.encode())
        logging.info("socker.py!client::create_task(), Sent: %s", client_to_server_message)
        
        message_from_server = str(client.recv(1024), encoding='utf-8')
        logging.info("socker.py!client::create_task(), Received: %s", message_from_server)
        client.close()

    def send_command(self, taskid, json_data):
        logging.info("socker.py!client::send_command(), TaskId=%d Host=%s Port=%d", taskid, self.host_ip, self.host_port)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((self.host_ip, self.host_port))

        client_to_server_message = self.command.json_to_str(json_data)
        client.send(client_to_server_message.encode())
        logging.info("socker.py!client::send_command(), Sent: %s", taskid, client_to_server_message)
        
        message_from_server = str(client.recv(1024), encoding='utf-8')
        logging.info("socker.py!client::send_command(), Received: %s", taskid, message_from_server)
        client.close()

    def send(self, taskid, message):
        logging.info("socker.py!client::send(), TaskId=%d Host=%s Port=%d", taskid, self.host_ip, self.host_port)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((self.host_ip, self.host_port))
        client_to_server_message = message
        client.send(client_to_server_message.encode())
        logging.info("socker.py!client::send(), Sent: %s", taskid, client_to_server_message)

        serv_mesg = str(client.recv(1024), encoding='utf-8')
        logging.info("socker.py!client::send(), Received: %s", taskid, serv_mesg)
        client.close()