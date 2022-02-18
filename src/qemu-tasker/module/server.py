# -*- coding: utf-8 -*-
from ast import Or
from email import message
import socket
import threading
import time
import logging
import json

from module import qemu
from module import config

class server:
    def __init__(self, socket_addr:config.socket_address):

        # Connection
        self.tcp_conn = None
        self.socket_addr = socket_addr
        self.occupied_ports = []

        # Status
        self.is_started = True
        
        # QEMU instance
        self.task_index = 0
        self.task_base_id = 10000                
        self.qemu_inst_list = []
        self.qemu_inst_list_killing_waiting = []

        # Thread objects
        self.thread_task = None 
        self.thread_postpone  = None
        self.thread_tcp = None

    def __del__(self):
        for qemu_inst in self.qemu_inst_list:
            qemu_inst.kill()

        for qemu_inst in self.qemu_inst_list_killing_waiting:
            qemu_inst.kill()

        self.is_started = False
        self.tcp_conn.close()

        self.thread_tcp = None
        self.thread_task = None 
        self.thread_postpone = None
        

    def stop(self):
        self.is_started = False

    def start(self):

        # Check and count longlife.
        self.thread_task = threading.Thread(target = self.thread_routine_longlife_counting)
        self.thread_task.setDaemon(True)
        self.thread_task.start()

        # Kill and clear killing waiting list.
        self.thread_postpone = threading.Thread(target = self.thread_routine_killing_waiting)
        self.thread_postpone.setDaemon(True)
        self.thread_postpone.start()

        # Wait connections and commands from clients.
        self.thread_tcp = threading.Thread(target = self.thread_routine_waiting_commands)
        self.thread_tcp.setDaemon(True)
        self.thread_tcp.start()        
        self.thread_tcp.join()

    def get_bool(self, result):
        if result:
            return "True "
        else:
            return "False"

    def thread_routine_longlife_counting(self):	
        print("{}● thread_routine_longlife_counting{}".format("", " ..."))

        while self.is_started:
            time.sleep(1)
           
            print('--------------------------------------------------------------------------------')
            print('QEMU instance number = {}'.format(len(self.qemu_inst_list)))
            for qemu_inst_obj in self.qemu_inst_list:
                qemu_inst:qemu.qemu_instance = qemu_inst_obj

                if qemu_inst.longlife > 0:
                    is_qmp_connected = self.get_bool(qemu_inst.is_qmp_connected())
                    is_ssh_connected = self.get_bool(qemu_inst.is_ssh_connected())

                    print('  QEMU TaskId:{} Ports:{} QMP:{} SSH:{} Longlife:{}(s) {}'.format(
                            qemu_inst.taskid,
                            qemu_inst.fwd_ports.toJSON(), 
                            is_qmp_connected, 
                            is_ssh_connected,
                            qemu_inst.longlife, 
                            qemu_inst.status))

                    qemu_inst.decrease_longlife()                    

                else:
                    self.qemu_inst_list_killing_waiting.append(qemu_inst)
                    self.qemu_inst_list.remove(qemu_inst)

    def thread_routine_killing_waiting(self):
        print("{}● thread_routine_killing_waiting{}".format("", " ..."))

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

    def find_target_instance(self, taskid) -> qemu.qemu_instance:
        target_qemu_inst = None
        for qemu_inst in self.qemu_inst_list:
            if qemu_inst.taskid == taskid:
                target_qemu_inst = qemu_inst
                break
        return target_qemu_inst

    def get_wrong_taskid_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : "wrong taskid",
            "stdout"    : ""
        }
        return reply_data

    def get_ssh_not_ready_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : "SSH connection is not ready",
            "stdout"    : ""
        }
        return reply_data

    def get_qmp_not_ready_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : "QMP connection is not ready",
            "stdout"    : ""
        }
        return reply_data

    def get_unsupported_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : "Unsupported command",
            "stdout"    : ""
        }
        return reply_data

    def command_to_exec(self, command:config.exec_command):
        qemu_inst = self.find_target_instance(command.taskid)
        if None == qemu_inst:
            print("{}● get_wrong_taskid_reply_data{}".format("  ", " !!!"))
            return self.get_wrong_taskid_reply_data(command.taskid)
        elif not qemu_inst.is_ssh_connected():
            print("{}● get_ssh_not_ready_reply_data{}".format("  ", " !!!"))
            return self.get_ssh_not_ready_reply_data(command.taskid)
        else:         
            result = qemu_inst.send_exec(command.exec_args)
            reply_data = {
                "taskid"    : command.taskid,
                "result"    : result,
                "errcode"   : 0,
                "stderr"    : qemu_inst.stderr,
                "stdout"    : qemu_inst.stdout
            }
            return reply_data

    def command_to_kill(self, kill_cmd:config.kill_command):
        qemu_inst = self.find_target_instance(kill_cmd.toJSON)
        if None == qemu_inst:
            return self.get_wrong_taskid_reply_data(kill_cmd.toJSON)
        else:                        
            self.qemu_inst_list.remove(qemu_inst)
            self.qemu_inst_list_killing_waiting.append(qemu_inst)
            reply_data = {
                "taskid"    : kill_cmd.toJSON,
                "result"    : qemu_inst.kill(),
                "errcode"   : qemu_inst.errcode,
                "stderr"    : qemu_inst.stderr,
                "stdout"    : qemu_inst.stdout
            }
            return reply_data

    def command_to_kill_all(self, kill_cmd:config.kill_command):

        kill_numb = 0
        for qemu_inst in self.qemu_inst_list:            
            self.qemu_inst_list_killing_waiting.append(qemu_inst)
            kill_numb = kill_numb + 1

        self.qemu_inst_list.clear()
        
        reply_data = {
            "taskid"    : kill_cmd.toJSON,
            "result"    : True,
            "errcode"   : 0,
            "stderr"    : "",
            "stdout"    : "{} QEMU instance was/were killed.".format(kill_numb) }
        
        return reply_data

    def command_to_qmp(self, qmp_cmd:config.qmp_command):
        qemu_inst = self.find_target_instance(qmp_cmd.taskid)                    
        if None == qemu_inst:
            return self.get_wrong_taskid_reply_data(qmp_cmd.taskid)
        if not qemu_inst.is_qmp_connected():
            return self.get_qmp_not_ready_reply_data(qmp_cmd.taskid)
        else:     
            recv_text = qemu_inst.send_qmp(qmp_cmd)            

            result  = True
            errcode = 0
            stderr  = ""

            if 0 == len(recv_text):
                result  = False
                errcode = -1
                stderr  = "no return"

            reply_data = {
                "taskid"    : qmp_cmd.taskid,
                "result"    : result,
                "errcode"   : errcode,
                "stderr"    : stderr,
                "stdout"    : recv_text,
            }
            return reply_data

    def thread_routine_waiting_commands(self):
        print("{}● thread_worker_tcp{}".format("", " ..."))
        print("  socket_addr.addr={}".format(self.socket_addr.addr))
        print("  socket_addr.port={}".format(self.socket_addr.port))

        self.tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_conn.bind((self.socket_addr.addr, self.socket_addr.port))
        self.tcp_conn.listen(10)

        while True:            
            conn, addr = self.tcp_conn.accept()
            client_mesg = str(conn.recv(1024), encoding='utf-8')
            
            print("{}● conn={}".format("  ", conn))
            print("{}● client_mesg={}".format("  ", client_mesg))
            
            if client_mesg.startswith("{\"request\":"):
                
                client_data = json.loads(client_mesg)
                print("{}● client_data={}".format("  ", client_data))

                resp_text = ""

                # Start
                if config.command_kind().start == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    start_cfg = config.start_config(client_data['request']['data'])                    
                    taskid:int = self.get_new_taskid()                    
                    qemu_inst = qemu.qemu_instance(self.socket_addr, taskid, start_cfg.cmd)
                    self.qemu_inst_list.append(qemu_inst)

                    reply_data = {
                        "taskid"    : taskid,
                        "fwd_ports" : qemu_inst.fwd_ports.toJSON(),
                        "result"    : (0 == qemu_inst.errcode),
                        "errcode"   : qemu_inst.errcode,
                        "stderr"    : qemu_inst.stderr,
                        "stdout"    : qemu_inst.stdout,
                    }
                    start_r = config.start_reply(reply_data)
                    start_resp = config.start_response(start_r)
                    resp_text = start_resp.toTEXT()

                # Exec
                elif config.command_kind().exec == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    exec_cfg = config.exec_config(client_data['request']['data'])
                    reply_data = self.command_to_exec(exec_cfg.cmd)
                    default_r = config.default_reply(reply_data)
                    default_resp = config.default_response(client_data['request']['command'], default_r)
                    resp_text = default_resp.toTEXT()

                # Kill
                elif config.command_kind().kill == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    kill_cfg = config.kill_config(client_data['request']['data'])                    
                    
                    if kill_cfg.cmd.killall:                    
                        reply_data = self.command_to_kill_all(kill_cfg.cmd)                    
                    else:
                        reply_data = self.command_to_kill(kill_cfg.cmd)

                    default_r = config.default_reply(reply_data)
                    default_resp = config.default_response(client_data['request']['command'], default_r)
                    resp_text = default_resp.toTEXT()
                    
                # QMP
                elif config.command_kind().qmp == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    qmp_cfg = config.qmp_config(client_data['request']['data'])
                    reply_data = self.command_to_qmp(qmp_cfg.cmd)
                    default_r = config.default_reply(reply_data)
                    default_resp = config.default_response(client_data['request']['command'], default_r)
                    resp_text = default_resp.toTEXT()

                # Others
                else:
                    reply_data = self.get_unsupported_reply_data()
                    bad_r = config.bad_reply(reply_data)
                    bad_resp = config.bad_response(bad_r)
                    resp_text = bad_resp.toTEXT()

                print("{}● resp_text={}".format("  ", resp_text))
                conn.send(bytes(resp_text, encoding="utf-8"))
                conn.close()
                conn = None