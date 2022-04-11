# -*- coding: utf-8 -*-
from doctest import FAIL_FAST
import os
import json
import platform
import socket
import logging

from time import sleep
from datetime import datetime

#
# ssh2-python
#
from ssh2.session import Session
from ssh2.sftp import LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR
from ssh2.session import Session
from ssh2.sftp import LIBSSH2_FXF_CREAT, LIBSSH2_FXF_WRITE, \
    LIBSSH2_SFTP_S_IRUSR, LIBSSH2_SFTP_S_IRGRP, LIBSSH2_SFTP_S_IWUSR, \
    LIBSSH2_SFTP_S_IROTH

#
# Internal modules
#
from module import config
from module.path import OsdpPath
from module.sshclient import ssh_link




# =================================================================================================
#
# =================================================================================================
class governor_client_base:
  def __init__(self):
        pass



# =================================================================================================
#
# =================================================================================================
class mock_governor_client(governor_client_base):

    def __init__(self, host_addr:config.socket_address, mock_return_data):
        self.mock_return_data = mock_return_data


    def send_control_command(self, cmd_kind:config.command_kind, cmd_data, is_json_report:bool) -> config.transaction_capsule:
        return self.mock_return_data


# =================================================================================================
#
# =================================================================================================
class governor_client(governor_client_base):

    def __init__(self, host_addr:config.socket_address):
        self.BUFF_SIZE = 4096

        self.path = OsdpPath()
        self.ssh_link = ssh_link()
        self.host_addr = host_addr


    def __del__(self):
        pass


    def send_control_command(self, cmd_kind:config.command_kind, cmd_data, is_json_report:bool) -> config.transaction_capsule:
        request_capsule = config.transaction_capsule(config.action_kind().request, cmd_kind, data=cmd_data)

        self.conn_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn_tcp.connect((self.host_addr.address, self.host_addr.port))
        self.conn_tcp.send(request_capsule.toTEXT().encode())

        received = b''
        while True:
            sleep(0.1)
            part = self.conn_tcp.recv(self.BUFF_SIZE)
            received = received + part
            if len(part) < self.BUFF_SIZE:
                try:
                    json.loads(str(received, encoding='utf-8'))
                    break
                except Exception as e:
                    continue

        self.conn_tcp.close()

        response_text = str(received, encoding='utf-8')
        response_json = json.loads(response_text)

        if is_json_report:
            if True == is_json_report:
                print(json.dumps(response_json, indent=2, sort_keys=True))
            else:
                print("[qemu-tasker] returned errcode: {}".format(response_json.result.errcode))

        response_capsule = config.config().toCLASS(response_text)
        return response_capsule


    # def send_transfer_command(self,
    #                           cmd_kind:config.command_kind,
    #                           cmd_data,
    #                           is_json_report:bool=False) -> config.transaction_capsule:
    #     cmdret = config.command_return()

    #     # Retrieve SSH information by sending a STATUS command.
    #     status_response_capsule = self.send_control_command(
    #                                     config.command_kind().status,
    #                                     config.status_command_request_data(cmd_data.taskid),
    #                                     None)

    #     if status_response_capsule.data:
    #         status_data:config.status_command_response_data = status_response_capsule.data
    #         is_connected = self.ssh_link.connect(status_data.ssh.target.address,
    #                                              status_data.forward.ssh,
    #                                              status_data.ssh.account.username,
    #                                              status_data.ssh.account.password)
    #         if not is_connected:
    #             cmdret.errcode = -1
    #             cmdret.error_lines.append('Failed to establish a SSH connection !!!')
    #     else:
    #         cmdret.errcode = -2
    #         cmdret.error_lines.append('response_capsule.data is None !!!')

    #     tx_capsule = None
    #     if cmdret.errcode == 0:
    #         if   cmd_kind == config.command_kind().list:
    #             tx_capsule = self.exec_list_command(cmd_data, status_data)
    #         elif cmd_kind == config.command_kind().upload:
    #             tx_capsule = self.exec_upload_command(cmd_data, status_data)
    #         elif cmd_kind == config.command_kind().download:
    #             tx_capsule = self.exec_download_command(cmd_data, status_data)
    #     else:
    #         tx_capsule = config.transaction_capsule(config.action_kind().response, cmd_kind, cmdret, None)

    #     if is_json_report:
    #         if True == is_json_report:
    #             print(json.dumps(tx_capsule.toJSON(), indent=2, sort_keys=True))
    #         else:
    #             print("[qemu-tasker] returned errcode: {}".format(tx_capsule.result.errcode))

    #     return tx_capsule


    # def exec_list_command(self,
    #                       cmd_data:config.list_command_request_data,
    #                       status_resp_data:config.status_command_response_data):
    #     guest_work_dir = status_resp_data.guest_info.workdir_name

    #     cmdret = config.command_return()
    #     if None == cmd_data.dstdir:
    #         cmdret.errcode = -1
    #         cmdret.error_lines.append("The specific dstdir cannot be EMPTY !!!")

    #     dstpath = os.path.join(guest_work_dir, cmd_data.dstdir)
    #     dstpath = self.path.normpath(dstpath)
    #     cmdret.info_lines.append("dstpath={}".format(dstpath))

    #     if cmdret.errcode == 0:
    #         logging.info('trying to call self.ssh_link.exists() function. (dstpath={})'.format(dstpath))
    #         cmdret_exist = self.ssh_link.exists(dstpath)
    #         if cmdret_exist.errcode != 0:
    #             cmdret.error_lines.append("The path is not exist !!! (dstpath={})".format(dstpath))
    #             cmdret.errcode = cmdret_exist.errcode
    #             cmdret.info_lines.extend(cmdret_exist.info_lines)
    #             cmdret.error_lines.extend(cmdret_exist.error_lines)

    #     readdir_data = None
    #     if cmdret.errcode == 0:
    #         logging.info('trying to call self.ssh_link.readdir() function. (dstpath={})'.format(dstpath))
    #         cmdret_readdir = self.ssh_link.readdir(dstpath)
    #         if cmdret_readdir.errcode != 0:
    #             cmdret.error_lines.append("Failed to call readdir() !!! (dstpath={})".format(dstpath))
    #         cmdret.errcode = cmdret_readdir.errcode
    #         cmdret.info_lines.extend(cmdret_readdir.info_lines)
    #         cmdret.error_lines.extend(cmdret_readdir.error_lines)
    #         readdir_data = cmdret_readdir.data
    #         cmdret.info_lines.append("{} file were found.".format(len(readdir_data)))

    #     resp_data = config.list_command_response_data(cmd_data.taskid, readdir_data)
    #     tx_capsule = config.transaction_capsule (config.action_kind().response,
    #                                                   config.command_kind().list,
    #                                                   cmdret,
    #                                                   resp_data)
    #     return tx_capsule


    # def exec_download_command(self,
    #                           cmd_data:config.download_command_request_data,
    #                           status_resp_data:config.status_command_response_data):
    #     guest_work_dir = status_resp_data.guest_info.workdir_name

    #     cmdret = config.command_return()
    #     if None == cmd_data.dstdir:
    #         cmdret.errcode = -1
    #         cmdret.error_lines.append("The specific dstdir cannot be EMPTY !!!")

    #     if cmdret.errcode == 0:
    #         if not os.path.exists(cmd_data.dstdir):
    #             cmdret.errcode = -2
    #             cmdret.error_lines.append("The specific dstdir directory is not there !!!")
    #             cmdret.error_lines.append("dstdir={}".format(cmd_data.dstdir))

    #     for file_path in cmd_data.files:
    #         if self.path.is_abs(file_path):
    #             cmdret.errcode = -3
    #             cmdret.error_lines.append("Absolution path is not allowed!!! ({})".format(file_path))

    #     if cmdret.errcode == 0:
    #         try:
    #             for file_path in cmd_data.files:

    #                 cmdret.info_lines.append('--------------------------------------------------')

    #                 # Source path
    #                 src_path = os.path.join(guest_work_dir, file_path)
    #                 src_path = self.path.normpath_posix(src_path)
    #                 cmdret.info_lines.append("src_path={}".format(src_path))


    #                 # Check source exist
    #                 cmdret_exist = self.ssh_link.exists(src_path)
    #                 if cmdret_exist.errcode != 0:
    #                     cmdret.errcode = cmdret_exist.errcode
    #                     cmdret.info_lines.extend(cmdret_exist.info_lines)
    #                     cmdret.info_lines.extend(cmdret_exist.info_lines)


    #                 # Destination path
    #                 dst_path = '.'
    #                 if cmd_data.dstdir:
    #                     dst_path = self.path.realpath(cmd_data.dstdir)
    #                 basename = self.path.basename(file_path)
    #                 dst_path = self.path.normpath(os.path.join(dst_path, basename))
    #                 cmdret.info_lines.append("dst_path={}".format(dst_path))


    #                 # Download
    #                 if 0 == cmdret_exist.errcode:
    #                     cmdret_download = self.ssh_link.download(src_path, dst_path)
    #                     cmdret.errcode = cmdret_download.errcode
    #                     cmdret.info_lines.extend(cmdret_download.info_lines)
    #                     cmdret.error_lines.extend(cmdret_download.error_lines)

    #                 if cmdret.errcode != 0:
    #                     break

    #         except Exception as e:
    #             cmdret.error_lines.append(str(e))
    #             logging.info(str(e))

    #     resp_data = config.download_command_response_data(cmd_data.taskid)
    #     tx_capsule = config.transaction_capsule(config.action_kind().response,
    #                                                  config.command_kind().download,
    #                                                  cmdret,
    #                                                  resp_data)
    #     return tx_capsule


    # def exec_upload_command(self,
    #                         cmd_data:config.upload_command_request_data,
    #                         status_resp_data:config.status_command_response_data):
    #     total_cmdret = config.command_return()


    #     for file_path in cmd_data.files:
    #         file_path = os.path.realpath(file_path)
    #         if not os.path.exists(file_path):
    #             total_cmdret.error_lines.append("An input file is not existing !!! (file_path={})".format(file_path))
    #             total_cmdret.errcode = -1

    #     if total_cmdret.errcode== 0:

    #         try:
    #             guest_os_kind  = status_resp_data.guest_info.os_kind
    #             guest_work_dir = status_resp_data.guest_info.workdir_name

    #             guest_dstdir = guest_work_dir
    #             if cmd_data.dstdir:
    #                 guest_dstdir = self.path.normpath(os.path.join(guest_dstdir, cmd_data.dstdir))
    #                 total_cmdret.info_lines.append("guest_dstdir={}".format(guest_dstdir))
    #                 mkdir_cmdret = self.ssh_link.mkdir(guest_dstdir)
    #                 total_cmdret.errcode = mkdir_cmdret.errcode
    #                 total_cmdret.error_lines.extend(mkdir_cmdret.error_lines)
    #                 total_cmdret.info_lines.extend(mkdir_cmdret.info_lines)

    #             if 0 == total_cmdret.errcode:
    #                 for file_path in cmd_data.files:
    #                     file_path = os.path.realpath(file_path)

    #                     if platform.system() == 'Windows':
    #                         file_path = self.path.normpath_windows(file_path)
    #                     else:
    #                         file_path = self.path.normpath_posix(file_path)

    #                     basename = self.path.basename(file_path)

    #                     total_cmdret.info_lines.append('--------------------------------------------------')
    #                     total_cmdret.info_lines.append('guest_os_kind={}'.format(guest_os_kind))
    #                     total_cmdret.info_lines.append('file_path={}'.format(file_path))

    #                     target_path = self.path.normpath(os.path.join(guest_dstdir, basename), guest_os_kind)
    #                     upload_cmdret = self.ssh_link.upload(file_path, target_path)

    #                     total_cmdret.errcode = total_cmdret.errcode
    #                     if total_cmdret.errcode != 0:
    #                         total_cmdret.info_lines.extend(upload_cmdret.info_lines)
    #                         total_cmdret.error_lines.extend(upload_cmdret.error_lines)
    #                         break

    #         except Exception as e:
    #             total_cmdret.error_lines.append(str(e))
    #             logging.info(str(e))

    #     resp_data:config = config.upload_command_response_data(cmd_data.taskid)
    #     tx_capsule = config.transaction_capsule(config.action_kind().response,
    #                                                  config.command_kind().upload,
    #                                                  total_cmdret,
    #                                                  resp_data)
    #     return tx_capsule

    #==========================================================================
    #==========================================================================
    #==========================================================================

