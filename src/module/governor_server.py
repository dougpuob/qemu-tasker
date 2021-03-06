# -*- coding: utf-8 -*-
import os
import json
import time
import socket
import logging
import threading

from inspect import currentframe, getframeinfo

from module import qemu
from module import config
from module.path import OsdpPath



# =================================================================================================
#
# =================================================================================================
class governor_server_base:
  def __init__(self):
    pass

  def __del__(self):
    pass

  def terminate(self):
    pass

  def stop(self):
    pass

  def start(self, config_path:str):
    pass

  def get_new_taskid(self):
    pass

  def find_target_instance(self, taskid) -> qemu.qemu_instance:
    pass

  def command_to_exec(self,
                        qemu_inst:qemu.qemu_instance,
                        cmd_data:config.exec_command_request_data):
    pass

  def command_to_kill(self,
                        qemu_inst:qemu.qemu_instance,
                        kill_data:config.kill_command_request_data):
    pass

  def command_to_qmp(self,
                        qemu_inst:qemu.qemu_instance,
                        qmp_data:config.qmp_command_request_data):
    pass

  def command_to_push(self,
                        qemu_inst:qemu.qemu_instance,
                        push_data:config.push_command_request_data):
    pass

  def command_to_status(self,
                            qemu_inst:qemu.qemu_instance,
                            status_data:config.status_command_request_data):
    pass

  def command_to_info(self,
                        info_data:config.info_command_request_data):
    pass

  def create_qemu_instance(self, pushpool_path:str, taskid:int, start_data:config.start_command_request_data):
    pass

  def apply_server_variables(self, cmd_info:config.command_arguments):
    pass

  def apply_client_variables(self, cmd_info:config.command_arguments, start_data:config.start_command_request_data):
    pass

  def verify_arguments(self):
    pass

  def get_command_return(self, errcode:int, error_text:str) -> config.command_return:
    pass

  def clear_qemu_instance(self, taskid:int, qemu_inst:qemu.qemu_instance) -> config.command_return:
    pass

  def check_and_clear_qemu_instance(self, taskid:int, qemu_inst:qemu.qemu_instance) -> config.command_return:
    pass



# =================================================================================================
#
# =================================================================================================
class governor_server_mock(governor_server_base):
  def __init__(self, socket_addr:config.socket_address):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((socket_addr.address, socket_addr.port))
        s.listen(1)

        # conn, addr = s.accept()
        # print 'Connected by', addr
        # while 1:
        # data = conn.recv(1024)
        # if not data: break
        # conn.sendall(data)
        # conn.close()


# =================================================================================================
#
# =================================================================================================
class governor_server(governor_server_base):
    def __init__(self, setting):

        # New Config
        self.setting = setting
        self.addr_info = config.socket_address(self.setting.Governor.Address, self.setting.Governor.Port)
        self.path = OsdpPath()
        self.server_variables_dict = {}

        # Connection
        self.socket_addr = self.addr_info
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
            self.listen_tcp_conn.shutdown()
            self.listen_tcp_conn.close()


    def stop(self):
        logging.info("STOP!!!")
        self.is_started = False


    def start(self):

        # Apply pathes in config if exist.
        server_pushpool_dir = ''
        server_qcow2image_dir = ''

        for idx, val in enumerate(self.setting.Governor.Variables):
            if val.Name == "SERVER_PUSHPOOL_DIR":
                server_pushpool_dir = self.path.normpath(self.path.realpath(val.Value))
            elif val.Name == "SERVER_QCOW2_IMAGE_DIR":
                server_qcow2image_dir = self.path.normpath(self.path.realpath(val.Value))

        if os.path.exists(server_pushpool_dir):
            self.server_pushpool_dir = server_pushpool_dir

        if os.path.exists(server_qcow2image_dir):
            self.server_qcow2image_dir = server_qcow2image_dir


        # Create selected directories if not eixst.
        if not os.path.exists(self.server_pushpool_dir):
            os.makedirs(self.server_pushpool_dir)

        if not os.path.exists(self.server_qcow2image_dir):
            os.makedirs(self.server_qcow2image_dir)

        logging.info("self.server_pushpool_dir   = {} ({})".format(self.server_pushpool_dir, os.path.exists(self.server_pushpool_dir)))
        logging.info("self.server_qcow2image_dir = {} ({})".format(self.server_qcow2image_dir, os.path.exists(self.server_qcow2image_dir)))
        if os.path.exists(self.server_qcow2image_dir):
            idx = 0
            dirs = os.listdir(self.server_qcow2image_dir)
            dirs.sort(reverse=True)
            for dir in dirs:
                if dir.lower().endswith('.qcow2'):
                    abs_path = os.path.join(self.server_qcow2image_dir, dir)
                    logging.info("  qcow2image[{}] = {}".format(idx, abs_path))
                    idx = idx + 1

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


    def get_bool_str(self, result):
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
                    print('  QEMU TaskId:{} Pid:{} Ports:{} QMP:{} PUP:{} OS:{} Longlife:{}(s) {}'.format(
                            qemu_inst.taskid,
                            qemu_inst.qemu_pid,
                            qemu_inst.forward_port.toJSON(),
                            self.get_bool_str(qemu_inst.is_qmp_connected()),
                            self.get_bool_str(qemu_inst.is_pup_connected()),
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


    def find_target_instance(self, taskid):
        target_qemu_inst = None
        for qemu_inst in self.qemu_instance_list:
            if qemu_inst.taskid == taskid:
                target_qemu_inst = qemu_inst
                break
        return target_qemu_inst


    def command_to_kill(self,
                        qemu_inst:qemu.qemu_instance,
                        kill_data:config.kill_command_request_data):
        if qemu_inst and kill_data:
            self.qemu_instance_list.remove(qemu_inst)
            result = qemu_inst.kill()
            resp_data = config.kill_command_response_data(kill_data.taskid)
            return resp_data
        return None


    def command_to_qmp(self,
                       qemu_inst:qemu.qemu_instance,
                       qmp_data:config.qmp_command_request_data):
        if qemu_inst and qmp_data:
            ret_bool = qemu_inst.send_qmp(qmp_data)
            if False == ret_bool:
                qemu_inst.result.errcode = -1
                qemu_inst.result.error_lines.append('no return !!!')

            resp_data = config.qmp_command_response_data(qmp_data.taskid)
            return resp_data
        return None


    def command_to_push(self,
                        qemu_inst:qemu.qemu_instance,
                        push_data:config.push_command_request_data):
        if qemu_inst and push_data:
            qemu_inst.send_push(push_data)
            resp_data = config.push_command_response_data(push_data.taskid)
            return resp_data
        return None


    def command_to_status(self,
                          qemu_inst:qemu.qemu_instance,
                          status_data:config.status_command_request_data):
        if qemu_inst and status_data:
            resp_data = config.status_command_response_data(
                                        status_data.taskid,
                                        qemu_inst.qemu_pid,
                                        qemu_inst.forward_port,
                                        qemu_inst.server_info,
                                        qemu_inst.guest_info,
                                        qemu_inst.connections_status,
                                        qemu_inst.qemu_full_cmdargs,
                                        qemu_inst.status)
            return resp_data
        return None


    def command_to_info(self,
                        info_data:config.info_command_request_data):
        qcow2_files = []
        files = os.listdir(self.server_qcow2image_dir)
        for file in files:
            if file.endswith(".qcow2"):
                qcow2_files.append(file)

        resp_data = config.info_command_response_data(
                                    self.setting.Governor.Variables,
                                    qcow2_files)
        return resp_data


    def thread_routine_listening_connections(self):
        logging.info("thread_routine_listening_connections ...")
        logging.info("  socket_addr.address={}".format(self.socket_addr.address))
        logging.info("  socket_addr.port={}".format(self.socket_addr.port))

        try:
            self.listen_tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listen_tcp_conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listen_tcp_conn.bind((self.socket_addr.address, self.socket_addr.port))
            self.listen_tcp_conn.listen(10)

            while self.is_started:
                new_conn, new_addr = self.listen_tcp_conn.accept()
                thread_for_command = threading.Thread(target = self.thread_routine_processing_command, args=(new_conn,))
                thread_for_command.setDaemon(True)
                thread_for_command.start()

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)


    def create_qemu_instance(self, pushpool_path:str, taskid:int, start_data:config.start_command_request_data):

        #
        # Check QCOW2 image dir path.
        #
        if not os.path.exists(self.server_qcow2image_dir):
            logging.error('QCOW2 image direcotyr found !!! (self.server_qcow2image_dir={})'.format(self.server_qcow2image_dir))
            return None

        image_filepath = self.path.normpath_posix(os.path.join(self.server_qcow2image_dir, start_data.qcow2filename))
        if not os.path.exists(image_filepath):
            logging.error('QCOW2 image file not found !!! (image_filepath={})'.format(image_filepath))
            return None

        #
        # Apply variables.
        #
        self.apply_server_variables(start_data.cmd)
        self.apply_client_variables(start_data.cmd, start_data)

        #
        # Go for it.
        #
        qemu_inst = qemu.qemu_instance(self.setting, pushpool_path, taskid, start_data)
        qemu_inst.wait_to_create()

        return qemu_inst


    def apply_server_variables(self, cmd_info:config.command_arguments):
        for idx, val in enumerate(cmd_info.arguments):
            for var in  self.setting.Governor.Variables:
                key_name = "${" + var.Name + "}"
                if val.find(key_name) != -1:
                    cmd_info.arguments[idx] = val.replace(key_name, var.Value)
        return cmd_info


    def apply_client_variables(self, cmd_info:config.command_arguments, start_data:config.start_command_request_data):
        qcow2filename = '${qcow2filename}'
        for idx, val in enumerate(cmd_info.arguments):
            if val.find(qcow2filename) != -1:
                cmd_info.arguments[idx] = val.replace(qcow2filename, start_data.qcow2filename)
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
                resp_capcsule = None
                incoming_capsule:config.transaction_capsule = config.config().toCLASS(incoming_message)

                # ------
                # Info
                # ------
                if config.command_kind().info == incoming_capsule.cmd_kind:
                    cmd_data:config.info_command_request_data = incoming_capsule.data
                    resp_data = self.command_to_info(cmd_data)

                # ------
                # Start
                # ------
                elif config.command_kind().start == incoming_capsule.cmd_kind:
                    cmd_data:config.start_command_request_data = incoming_capsule.data
                    qemu_inst = self.create_qemu_instance(self.server_pushpool_dir,
                                                          self.get_new_taskid(),
                                                          cmd_data)
                    self.qemu_instance_list.append(qemu_inst)
                    resp_data = config.start_command_response_data(
                                                        qemu_inst.taskid,
                                                        qemu_inst.qemu_pid,
                                                        qemu_inst.forward_port,
                                                        qemu_inst.server_info,
                                                        qemu_inst.guest_info,
                                                        qemu_inst.connections_status,
                                                        qemu_inst.qemu_full_cmdargs,
                                                        qemu_inst.status)
                # ------
                # Kill
                # ------
                elif config.command_kind().kill == incoming_capsule.cmd_kind:
                    cmd_data:config.kill_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_kill(qemu_inst, cmd_data)

                # # ------
                # # Exec
                # # ------
                # elif config.command_kind().exec == incoming_capsule.cmd_kind:
                #     cmd_data:config.exec_command_request_data = incoming_capsule.data
                #     qemu_inst = self.find_target_instance(cmd_data.taskid)
                #     cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                #     if cmdret.errcode == 0:
                #         resp_data = self.command_to_exec(qemu_inst, cmd_data)

                # ------
                # Status
                # ------
                elif config.command_kind().status == incoming_capsule.cmd_kind:
                    cmd_data:config.status_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    if qemu_inst:
                        cmdret = self.clear_qemu_instance(cmd_data.taskid, qemu_inst)
                        if cmdret.errcode == 0:
                            resp_data = self.command_to_status(qemu_inst, cmd_data)

                # ------
                # QMP
                # ------
                elif config.command_kind().qmp == incoming_capsule.cmd_kind:
                    cmd_data:config.qmp_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_qmp(qemu_inst, cmd_data)

                # ------
                # Push
                # ------
                elif config.command_kind().push == incoming_capsule.cmd_kind:
                    cmd_data:config.push_command_request_data = incoming_capsule.data
                    qemu_inst = self.find_target_instance(cmd_data.taskid)
                    cmdret = self.check_and_clear_qemu_instance(cmd_data.taskid, qemu_inst)
                    if cmdret.errcode == 0:
                        resp_data = self.command_to_push(qemu_inst, cmd_data)

                # ------
                # Others
                # ------
                elif config.command_kind().list == incoming_capsule.cmd_kind or \
                     config.command_kind().upload == incoming_capsule.cmd_kind or \
                     config.command_kind().download == incoming_capsule.cmd_kind:
                    error_text = "the '{}' command should not handle on server !!!".format(incoming_capsule.cmd_kind)
                    resp_capcsule = config.transaction_capsule(
                                                    config.action_kind().response,
                                                    incoming_capsule.cmd_kind,
                                                    self.get_command_return(-1, error_text),
                                                    resp_data)
                    return_capsule_text = resp_capcsule.toTEXT()
                    logging.error(error_text)


                #
                # Summary result then create coresponding error handling.
                #
                cmd_ret = None
                if config.command_kind().info == incoming_capsule.cmd_kind :
                    cmd_ret = config.command_return()
                elif None == qemu_inst:
                    cmd_ret = config.return_command_no_qemu_inst
                elif None == resp_data:
                    cmd_ret = config.return_command_no_resp_data
                else:
                    cmd_ret = qemu_inst.result

                resp_capcsule = config.transaction_capsule(config.action_kind().response,
                                                           incoming_capsule.cmd_kind,
                                                           cmd_ret,
                                                           resp_data)
                return_capsule_text = resp_capcsule.toTEXT()
                logging.info("return_capsule_text={}".format(return_capsule_text))
                conn.send(bytes(return_capsule_text, encoding="utf-8"))

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)


    def get_command_return(self, errcode:int, error_text:str) -> config.command_return():
        cmd_ret = config.command_return()
        cmd_ret.errcode = errcode
        cmd_ret.error_lines.append(error_text)
        return cmd_ret


    def clear_qemu_instance(self, taskid:int, qemu_inst:qemu.qemu_instance) -> config.command_return:
        cmdret = config.command_return()
        cmdret.info_lines.append('taskid={}'.format(taskid))

        if qemu_inst:
            qemu_inst.clear()

        return cmdret


    def check_and_clear_qemu_instance(self, taskid:int, qemu_inst:qemu.qemu_instance):
        cmdret = config.command_return()
        cmdret.info_lines.append('taskid={}'.format(taskid))

        if None == qemu_inst:
            cmdret.errcode = -10
            cmdret.error_lines.append('qemu_inst={}'.format(qemu_inst))
            logging.warning(cmdret)
        else:
            qemu_inst.clear()

        return cmdret


