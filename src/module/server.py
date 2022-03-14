# -*- coding: utf-8 -*-
import os
import json
import time
import socket
import logging
import threading


from module import qemu
from module import config_next
from module.path import OsdpPath


class server:
    def __init__(self, socket_addr:config_next.socket_address):

        #
        # New Config
        #
        self.addr_info = config_next.socket_address(socket_addr.addr, socket_addr.port)
        self.path = OsdpPath()
        self.server_variables_dict = {}

        # Connection
        self.socket_addr = socket_addr
        self.listen_tcp_conn = None
        self.accepted_conn_list = []

        # Resource
        self.occupied_ports = []
        self.server_pushpool_dir = "data/pushpool"
        self.server_qcow2image_dir = "data/images"

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
        logging.info("DEL!!!")

        self.terminate()

        self.is_started = False
        self.thread_tcp = None
        self.thread_task = None
        self.thread_postpone = None


    def terminate(self):
        logging.info("TERMINATE!!!")

        for qemu_inst in self.qemu_instance_list:
            qemu_inst.kill()

        self.is_started = False
        if self.listen_tcp_conn:
            self.listen_tcp_conn.close()


    def stop(self):
        logging.info("STOP!!!")
        self.is_started = False


    def start(self, config_path:str):
        logging.info("config_path={}".format(config_path))
        if os.path.exists(config_path):
            with open(config_path) as f:

                # Load JSON config file
                config = json.load(f)
                self.server_variables_dict = config
                logging.info("self.server_variables_dict={}".format(self.server_variables_dict))


                # Apply pathes in config if exist.
                server_pushpool_dir = self.path.realpath(config['SERVER_PUSHPOOL_DIR'])
                server_qcow2image_dir = self.path.realpath(config['SERVER_QCOW2_IMAGE_DIR'])

                if os.path.exists(server_pushpool_dir):
                    self.server_pushpool_dir = server_pushpool_dir

                if os.path.exists(server_qcow2image_dir):
                    self.server_qcow2image_dir = server_qcow2image_dir


                # Create selected directories if not eixst.
                if not os.path.exists(self.server_pushpool_dir):
                    os.makedirs(self.server_pushpool_dir)

                if not os.path.exists(self.server_qcow2image_dir):
                    os.makedirs(self.server_qcow2image_dir)

                logging.info("self.server_pushpool_dir   = {}".format(self.server_pushpool_dir))
                logging.info("self.server_qcow2image_dir = {}".format(self.server_qcow2image_dir))

        else:
            logging.exception('The config.json not found !!!')
            assert False, 'The config.json not found !!!'


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
        logging.info("thread_routine_longlife_counting ...")

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
                            qemu_inst.qemu_pid,
                            qemu_inst.forward_port.toJSON(),
                            is_qmp_connected,
                            is_ssh_connected,
                            qemu_inst.guest_info.os_kind,
                            qemu_inst.longlife,
                            qemu_inst.status))

                    qemu_inst.decrease_longlife()

                else:
                    qemu_inst.kill()


    def thread_routine_killing_waiting(self):
        logging.info("thread_routine_killing_waiting ...")

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


    def command_to_exec(self,
                        qemu_inst:qemu.qemu_instance,
                        cmd_data:config_next.exec_command_request_data):
        if qemu_inst and cmd_data:
            result = qemu_inst.send_exec(cmd_data, cmd_data.is_base64)
            resp_data = config_next.exec_command_response_data(cmd_data.taskid)
            return resp_data
        return None


    def command_to_kill(self,
                        qemu_inst:qemu.qemu_instance,
                        kill_data:config_next.kill_command_request_data):
        if qemu_inst and kill_data:
            self.qemu_instance_list.remove(qemu_inst)
            result = qemu_inst.kill()
            resp_data = config_next.kill_command_response_data(kill_data.taskid)
            return resp_data
        return None


    def command_to_qmp(self,
                       qemu_inst:qemu.qemu_instance,
                       qmp_data:config_next.qmp_command_request_data):
        if qemu_inst and qmp_data:
            ret_bool = qemu_inst.send_qmp(qmp_data)
            if False == ret_bool:
                qemu_inst.result.errcode = -1
                qemu_inst.result.error_lines.append('no return !!!')

            resp_data = config_next.qmp_command_response_data(qmp_data.taskid)
            return resp_data
        return None


    def command_to_push(self,
                        qemu_inst:qemu.qemu_instance,
                        push_data:config_next.push_command_request_data):
        if qemu_inst and push_data:
            qemu_inst.send_push(push_data)
            resp_data = config_next.push_command_response_data(push_data.taskid)
            return resp_data
        return None


    def command_to_status(self,
                          qemu_inst:qemu.qemu_instance,
                          status_data:config_next.status_command_request_data):
        if qemu_inst and status_data:
            resp_data = config_next.status_command_response_data(
                                        status_data.taskid,
                                        qemu_inst.qemu_pid,
                                        qemu_inst.forward_port,
                                        qemu_inst.ssh_info,
                                        qemu_inst.server_info,
                                        qemu_inst.guest_info,
                                        qemu_inst.is_qmp_connected(),
                                        qemu_inst.is_ssh_connected())
            # filepool = ''
            # if qemu_inst.guest_os_work_dir:
            #     filepool = os.path.join(qemu_inst.guest_os_work_dir, qemu_inst.pushdir_name)
            #     if qemu_inst.guest_info.os_kind == config_next.os_kind().windows:
            #         filepool = self.path.normpath_windows(filepool)
            #     else:
            #         filepool = self.path.normpath_posix(filepool)
            return resp_data
        return None


    def command_to_info(self,
                        info_data:config_next.info_command_request_data):
        qcow2_files = []
        files = os.listdir(self.server_qcow2image_dir)
        for file in files:
            if file.endswith(".qcow2"):
                qcow2_files.append(file)

        resp_data = config_next.info_command_response_data(
                                    self.server_variables_dict,
                                    qcow2_files)
        return resp_data


    def thread_routine_listening_connections(self):
        logging.info("thread_routine_listening_connections ...")
        logging.info("  socket_addr.addr={}".format(self.socket_addr.addr))
        logging.info("  socket_addr.port={}".format(self.socket_addr.port))

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
            logging.exception("exception={}".format(e))


    def create_qemu_instance(self, pushpool_path:str, taskid:int, start_data:config_next.start_command_request_data):
        self.apply_server_variables(start_data.cmd)
        qemu_inst = qemu.qemu_instance(self.socket_addr, pushpool_path, taskid, start_data)

        self.qemu_instance_list.append(qemu_inst)
        qemu_inst.wait_to_create()
        return qemu_inst


    def apply_server_variables(self, cmd_info:config_next.command_arguments):
        for idx, val in enumerate(cmd_info.arguments):
            for key in self.server_variables_dict:
                key_def = "${" + key + "}"
                if val.find(key_def) != -1:
                    cmd_info.arguments[idx] = val.replace(key_def, self.server_variables_dict[key])
        return cmd_info


    def verify_arguments(self):
        pass


    def thread_routine_processing_command(self, conn:socket.socket):
        logging.info("thread_routine_processing_command ...")

        try:
            incoming_message = str(conn.recv(2048), encoding='utf-8')

            logging.info("conn={}".format(conn))
            logging.info("incomming_message={}".format(incoming_message))

            if incoming_message.startswith("{\"act_kind\": \"request\""):

                qemu_inst = None
                resp_data = None
                return_capsule = None
                incoming_capsule:config_next.transaction_capsule = config_next.config().toCLASS(incoming_message)

                # ------
                # Info
                # ------
                if config_next.command_kind().info == incoming_capsule.cmd_kind:
                    cmd_data:config_next.info_command_request_data = incoming_capsule.data
                    resp_data = self.command_to_info(cmd_data)

                # ------
                # Start
                # ------
                elif config_next.command_kind().start == incoming_capsule.cmd_kind:
                    cmd_data:config_next.start_command_request_data = incoming_capsule.data
                    qemu_inst = self.create_qemu_instance(self.server_pushpool_dir,
                                                          self.get_new_taskid(),
                                                          cmd_data)
                    resp_data = config_next.start_command_response_data(
                                                        qemu_inst.taskid,
                                                        qemu_inst.qemu_pid,
                                                        qemu_inst.forward_port,
                                                        qemu_inst.ssh_info,
                                                        qemu_inst.server_info,
                                                        qemu_inst.guest_info,
                                                        qemu_inst.is_qmp_connected,
                                                        qemu_inst.is_ssh_connected)
                # ------
                # Kill
                # ------
                elif config_next.command_kind().kill == incoming_capsule.cmd_kind:
                    cmd_data:config_next.kill_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_kill(qemu_inst, cmd_data)

                # ------
                # Exec
                # ------
                elif config_next.command_kind().exec == incoming_capsule.cmd_kind:
                    cmd_data:config_next.exec_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_exec(qemu_inst, cmd_data)

                # ------
                # Status
                # ------
                elif config_next.command_kind().status == incoming_capsule.cmd_kind:
                    cmd_data:config_next.status_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_status(qemu_inst, cmd_data)

                # ------
                # QMP
                # ------
                elif config_next.command_kind().qmp == incoming_capsule.cmd_kind:
                    cmd_data:config_next.qmp_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_qmp(qemu_inst, cmd_data)

                # ------
                # Push
                # ------
                elif config_next.command_kind().push == incoming_capsule.cmd_kind:
                    cmd_data:config_next.push_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_push(qemu_inst, cmd_data)

                # ------
                # Others
                # ------
                elif config_next.command_kind().list == incoming_capsule.cmd_kind or \
                     config_next.command_kind().upload == incoming_capsule.cmd_kind or \
                     config_next.command_kind().download == incoming_capsule.cmd_kind:
                    error_text = "the '{}' command should not handle on server !!!".format(incoming_capsule.cmd_kind)
                    return_capsule = config_next.transaction_capsule(
                                                    config_next.action_kind().response,
                                                    incoming_capsule.cmd_kind,
                                                    self.get_command_return(-1, error_text),
                                                    resp_data)
                    return_capsule_text = return_capsule.toTEXT()
                    logging.error(error_text)


                # ------------------------------------------------------------------------
                if resp_data:
                    result = ''
                    if qemu_inst:
                        result = qemu_inst.result
                    else:
                        result = self.get_command_return(0, '')
                else:
                    err_text = "qemu_inst and resp_data are None !!!"
                    logging.error(err_text)
                    result = self.get_command_return(-9999, err_text)

                return_capsule = config_next.transaction_capsule(
                                                    config_next.action_kind().response,
                                                    incoming_capsule.cmd_kind,
                                                    result,
                                                    resp_data)
                return_capsule_text = return_capsule.toTEXT()
                logging.info("return_capsule_text={}".format(return_capsule_text))
                conn.send(bytes(return_capsule_text, encoding="utf-8"))

        except Exception as e:
            logging.exception("exception={}".format(e))


    def get_command_return(self, errcode:int, error_text:str) -> config_next.command_return():
        cmd_ret = config_next.command_return()
        cmd_ret.errcode = errcode
        cmd_ret.error_lines.append(error_text)
        return cmd_ret


    def check_and_clear_qemu_instance(self, taskid:int, qemu_inst:qemu.qemu_instance) -> config_next.command_return:
        cmdret = config_next.command_return()
        cmdret.info_lines.append('taskid={}'.format(taskid))

        if None == qemu_inst:
            cmdret.errcode = -10
            cmdret.error_lines.append('qemu_inst={}'.format(qemu_inst))
            logging.warning(cmdret)
        else:
            qemu_inst.clear()
            if not qemu_inst.is_ssh_connected():
                cmdret.errcode = -11
                cmdret.error_lines.append('The SSH connection is not created !!!')

        return cmdret


