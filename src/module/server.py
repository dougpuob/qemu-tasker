# -*- coding: utf-8 -*-
from ast import Or
from email import message
import os
import socket
import threading
import time
import logging
import json

from module import qemu
from module import config
from module.path import OsdpPath


class server:
    def __init__(self, socket_addr:config.socket_address):
        
        self.path = OsdpPath()

        # Connection
        self.socket_addr = socket_addr
        self.listen_tcp_conn = None
        self.accepted_conn_list = []

        # Resource
        self.occupied_ports = []
        self.filepool_basepath = ""

        # Status
        self.is_started = True

        # QEMU instance
        self.task_index = 0
        self.task_base_id = 10000
        self.qemu_instance_list = []

        # Thread objects
        self.thread_task = None
        self.thread_postpone  = None
        self.thread_tcp = None


    def __del__(self):
        print("DEL!!!")

        self.terminate()

        self.is_started = False
        self.thread_tcp = None
        self.thread_task = None
        self.thread_postpone = None


    def terminate(self):
        print("TERMINATE!!!")

        for qemu_inst in self.qemu_instance_list:
            qemu_inst.kill()

        self.is_started = False
        if self.listen_tcp_conn:
            self.listen_tcp_conn.close()


    def stop(self):
        print("STOP!!!")
        self.is_started = False


    def start(self, task_filepool:str):
        self.filepool_basepath = self.path.realpath(task_filepool)

        # Check and count longlife.
        self.thread_task = threading.Thread(target = self.thread_routine_checking_longlife)
        self.thread_task.setDaemon(True)
        self.thread_task.start()

        # Kill and clear killing waiting list.
        self.thread_postpone = threading.Thread(target = self.thread_routine_killing_waiting)
        self.thread_postpone.setDaemon(True)
        self.thread_postpone.start()

        # Wait connections and commands from clients.
        self.thread_tcp = threading.Thread(target = self.thread_routine_listening_connections)
        self.thread_tcp.setDaemon(True)
        self.thread_tcp.start()
        self.thread_tcp.join()


    def get_bool(self, result):
        if result:
            return "True "
        else:
            return "False"


    def thread_routine_checking_longlife(self):
        print("{}● thread_routine_longlife_counting{}".format("", " ..."))

        while self.is_started:
            time.sleep(1)

            print('--------------------------------------------------------------------------------')
            print('QEMU instance number = {}'.format(len(self.qemu_instance_list)))
            for qemu_inst_obj in self.qemu_instance_list:
                qemu_inst:qemu.qemu_instance = qemu_inst_obj

                if qemu_inst.longlife > 0:
                    is_qmp_connected = self.get_bool(qemu_inst.is_qmp_connected())
                    is_ssh_connected = self.get_bool(qemu_inst.is_ssh_connected())

                    print('  QEMU TaskId:{} Pid:{} Ports:{} QMP:{} SSH:{} OS:{}  Longlife:{}(s) {}'.format(
                            qemu_inst.taskid,
                            qemu_inst.pid,
                            qemu_inst.fwd_ports.toJSON(),
                            is_qmp_connected,
                            is_ssh_connected,
                            qemu_inst.guest_os_kind,
                            qemu_inst.longlife,
                            qemu_inst.status))

                    qemu_inst.decrease_longlife()

                else:
                    qemu_inst.kill()
                    self.qemu_instance_list.remove(qemu_inst)


    def thread_routine_killing_waiting(self):
        print("{}● thread_routine_killing_waiting{}".format("", " ..."))

        while self.is_started:
            # Handling killing waiting list.
            for qemu_inst_obj in self.qemu_instance_list:
                qemu_inst:qemu.qemu_instance = qemu_inst_obj
                is_alive = qemu_inst.is_proc_alive()
                if not is_alive:
                    self.qemu_instance_list.remove(qemu_inst)
                    qemu_inst.kill()

            time.sleep(1)


    def get_new_taskid(self):
        logging.info("socker.py!server::get_new_taskid()")

        self.task_index = self.task_index + 1
        return self.task_base_id + (self.task_index * 10)


    def find_target_instance(self, taskid) -> qemu.qemu_instance:
        target_qemu_inst = None
        for qemu_inst in self.qemu_instance_list:
            if qemu_inst.taskid == taskid:
                target_qemu_inst = qemu_inst
                break
        return target_qemu_inst


    def get_wrong_taskid_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : ["wrong taskid"],
            "stdout"    : ""
        }
        return reply_data


    def get_ssh_not_ready_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : ["SSH connection is not ready"],
            "stdout"    : ""
        }
        return reply_data


    def get_qmp_not_ready_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : ["QMP connection is not ready"],
            "stdout"    : ""
        }
        return reply_data


    def get_unsupported_reply_data(self, taskid):
        reply_data = {
            "taskid"    : taskid,
            "result"    : False,
            "errcode"   : -1,
            "stderr"    : ["Unsupported command"],
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
            
            result = qemu_inst.send_exec(command.exec_arg, command.is_base64)
            
            reply_data = {
                "taskid"    : command.taskid,
                "result"    : result,
                "errcode"   : qemu_inst.errcode,
                "stderr"    : qemu_inst.stderr,
                "stdout"    : qemu_inst.stdout
            }
            return reply_data


    def command_to_kill(self, kill_cmd:config.kill_command):
        qemu_inst = self.find_target_instance(kill_cmd.taskid)
        if None == qemu_inst:
            return self.get_wrong_taskid_reply_data(kill_cmd.toJSON)
        else:
            self.qemu_instance_list.remove(qemu_inst)
            result = qemu_inst.kill()
            reply_data = {
                "taskid"    : kill_cmd.taskid,
                "result"    : result,
                "errcode"   : qemu_inst.errcode,
                "stderr"    : qemu_inst.stderr,
                "stdout"    : qemu_inst.stdout
            }
            return reply_data


    def command_to_kill_all(self, kill_cmd:config.kill_command):
        kill_numb = 0
        for qemu_inst in self.qemu_instance_list:
            qemu_inst.kill()
            kill_numb = kill_numb + 1

        self.qemu_instance_list.clear()

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


    def command_to_push(self, push_cmd:config.push_command):
        qemu_inst = self.find_target_instance(push_cmd.taskid)
        if None == qemu_inst:
            return self.get_wrong_taskid_reply_data(push_cmd.taskid)
        if not qemu_inst.is_ssh_connected():
            return self.get_ssh_not_ready_reply_data(push_cmd.taskid)
        else:
            ret_cmd = qemu_inst.send_push(push_cmd)

            reply_data = {
                "taskid"    : push_cmd.taskid,
                "result"    : (0 == ret_cmd.errcode),
                "errcode"   : ret_cmd.errcode,
                "stderr"    : ret_cmd.error_lines,
                "stdout"    : ret_cmd.info_lines,
            }
            return reply_data


    def command_to_status(self, stat_cmd:config.status_command):
        qemu_inst:qemu.qemu_instance  = self.find_target_instance(stat_cmd.taskid)
        if None == qemu_inst:
            reply_data = {
                "result"  : False,
                "taskid"  : stat_cmd.taskid,
                "errcode" : 0 - stat_cmd.taskid,
                "stdout"  : [],
                "stderr"  : ["Cannot find the specific QEMU instance."],
                "status"  : config.task_status().unknown,
                "pid"     : 0,
                "fwd_ports" : { "qmp" : 0,
                                "ssh" : 0 },
                "ssh_info" : { "targetaddr" : "",
                               "targetport" : 0,
                               "username" : "",
                               "password" : ""},
                "host_pushpool" : "",
                "guest_os_kind" : "",
                "guest_pushpool" : "",
                "guest_work_dir" : "",
                "is_connected_qmp" : False,
                "is_connected_ssh" : False
                }
            return reply_data

        else:
            filepool = ''
            if qemu_inst.guest_os_work_dir:
                filepool = os.path.join(qemu_inst.guest_os_work_dir, qemu_inst.pushdir_name)
                if qemu_inst.guest_os_kind == config.os_kind().windows:
                    filepool = self.path.normpath_windows(filepool)
                else:
                    filepool = self.path.normpath_posix(filepool)
                    
            reply_data = {
                    "result"  : True,
                    "taskid"  : qemu_inst.taskid,
                    "errcode" : qemu_inst.errcode,
                    "stdout"  : qemu_inst.stdout,
                    "stderr"  : qemu_inst.stderr,
                    "status"  : qemu_inst.status,
                    "pid"     : qemu_inst.pid,
                    "fwd_ports" : { "qmp" : qemu_inst.fwd_ports.qmp,
                                    "ssh" : qemu_inst.fwd_ports.ssh },
                    "ssh_info" : { "targetaddr" : qemu_inst.socket_addr.addr,
                                   "targetport" : qemu_inst.fwd_ports.ssh,
                                   "username" : qemu_inst.start_cmd.ssh_login.username,
                                   "password" : qemu_inst.start_cmd.ssh_login.password},
                    "host_pushpool" : qemu_inst.host_pushdir_path,
                    "guest_os_kind" : qemu_inst.guest_os_kind,
                    "guest_pushpool" : qemu_inst.guest_os_pushpool_dir,
                    "guest_work_dir" : qemu_inst.guest_os_work_dir,
                    "is_connected_qmp" : qemu_inst.is_qmp_connected(),
                    "is_connected_ssh" : qemu_inst.is_ssh_connected()
                    }
            return reply_data


    def thread_routine_listening_connections(self):
        print("{}● thread_routine_listening_connections{}".format("", " ..."))
        print("  socket_addr.addr={}".format(self.socket_addr.addr))
        print("  socket_addr.port={}".format(self.socket_addr.port))

        try:
            self.listen_tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listen_tcp_conn.bind((self.socket_addr.addr, self.socket_addr.port))
            self.listen_tcp_conn.listen(10)

            while self.is_started:
                new_conn, new_addr = self.listen_tcp_conn.accept()
                thread_for_command = threading.Thread(target = self.thread_routine_processing_command, args=(new_conn,))
                thread_for_command.setDaemon(True)
                thread_for_command.start()

        except Exception as e:
            print("{}● exception={}".format(e))
            logging.info("{}● exception={}".format(e))


    def create_qemu_instance(self, taskid:int, start_cfg:config.start_config):
        qemu_inst = qemu.qemu_instance(self.socket_addr, taskid, start_cfg.cmd)
        self.qemu_instance_list.append(qemu_inst)
        qemu_inst.wait_to_create()
        return qemu_inst


    def thread_routine_processing_command(self, conn:socket.socket):
        print("{}● thread_routine_processing_command{}".format("", " ..."))

        try:
            client_mesg = str(conn.recv(2048), encoding='utf-8')

            print("{}● conn={}".format("  ", conn))
            print("{}● client_mesg={}".format("  ", client_mesg))

            if client_mesg.startswith("{\"request\":"):
                client_data = json.loads(client_mesg)

                resp_text = ""

                # Start
                if config.command_kind().start == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    start_cfg = config.start_config(client_data['request']['data'])
                    taskid:int = self.get_new_taskid()

                    qemu_inst = self.create_qemu_instance(taskid, start_cfg)

                    reply_data = {
                        "taskid"    : taskid,
                        "fwd_ports" : qemu_inst.fwd_ports.toJSON(),
                        "result"    : (0 == qemu_inst.errcode),
                        "errcode"   : qemu_inst.errcode,
                        "stderr"    : qemu_inst.stderr,
                        "stdout"    : qemu_inst.stdout,
                        "cwd"       : qemu_inst.guest_os_work_dir,
                        "os"        : qemu_inst.guest_os_kind
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
                    file_cfg = config.qmp_config(client_data['request']['data'])
                    reply_data = self.command_to_qmp(file_cfg.cmd)
                    default_r = config.default_reply(reply_data)
                    default_resp = config.default_response(client_data['request']['command'], default_r)
                    resp_text = default_resp.toTEXT()

                # push
                elif config.command_kind().push == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    stat_cfg = config.push_config(client_data['request']['data'])
                    reply_data = self.command_to_push(stat_cfg.cmd)
                    push_r = config.push_reply(reply_data)
                    push_resp = config.push_response(push_r)
                    resp_text = push_resp.toTEXT()

                # status
                elif config.command_kind().status == client_data['request']['command']:
                    print("{}● command_kind={}".format("  ", client_data['request']['command']))
                    stat_cfg = config.status_config(client_data['request']['data'])
                    reply_data = self.command_to_status(stat_cfg.cmd)
                    stat_r = config.status_reply(reply_data)
                    stat_resp = config.status_response(stat_r)
                    resp_text = stat_resp.toTEXT()

                # Others
                else:
                    reply_data = self.get_unsupported_reply_data()
                    bad_r = config.bad_reply(reply_data)
                    bad_resp = config.bad_response(bad_r)
                    resp_text = bad_resp.toTEXT()

            print("{}● resp_text={}".format("  ", resp_text))

            conn.send(bytes(resp_text, encoding="utf-8"))

        except Exception as e:
            print("{}● exception={}".format(e))
            logging.info("{}● exception={}".format(e))