# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-
from collections import UserList
from enum import Flag
import os
import json
from pickle import NONE
import time
import socket
import logging
import threading
import subprocess


from module.ftpclient import ftpclient
from module import config


# =================================================================================================
#
# =================================================================================================
class puppet_client_base():

  def __init__(self, host_addr:config.socket_address):
    self.BUFF_SIZE = 4096
    self.host_addr = host_addr
    self.cmd_tcp = None


  def __del__(self):
    pass


  def send(self, cmd_kind:config.command_kind, cmd_data) -> config.transaction_capsule:
    pass


# =================================================================================================
#
# =================================================================================================
class puppet_client_mock(puppet_client_base):
  def __init__(self):
    pass


# =================================================================================================
#
# =================================================================================================
class puppet_client(puppet_client_base):


    def __init__(self, taskid:int):
      self.BUFF_SIZE = 4096
      self.taskid = taskid
      self.cmd_socket = None
      self.ftp_obj = None
      self._is_cmd_connected = False
      self._is_ftp_connected = False


    def __del__(self):

      if self.cmd_socket:
        self.cmd_socket.close()

      if self.ftp_obj:
        self.ftp_obj.close()


    def is_cmd_connected(self):
        return self._is_cmd_connected


    def is_ftp_connected(self):
        return self._is_ftp_connected


    def connect_cmd(self, cmd_socket_addr:config.socket_address):

      return_result:bool = False

      try:
        logging.info("puppet client is trying to connect command socket ... (addr={0} port={1})".format(cmd_socket_addr.address, cmd_socket_addr.port))
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = self.cmd_socket.connect_ex((cmd_socket_addr.address, cmd_socket_addr.port))

        if result:
          return_result = False
        else:
          return_result = True

        self._is_cmd_connected = return_result

      except Exception as e:
        return_result = False
        logging.exception(str(e))

      finally:
        return return_result


    def connect_ftp(self,
                ftp_socket_addr:config.socket_address,
                ftp_user_info:config.account_information=None):

      return_result:bool = False

      try:
        if ftp_user_info:
          logging.info("puppet client is trying to connect FTP socket (username & password) ... (addr={0} port={1})".format(ftp_socket_addr.address, ftp_socket_addr.port))
          self.ftp_obj = ftpclient(ftp_socket_addr, ftp_user_info)
        else:
          # anonymous
          logging.info("puppet client is trying to connect FTP socket (anonymous)  ... (addr={0} port={1})".format(ftp_socket_addr.address, ftp_socket_addr.port))
          self.ftp_obj = ftpclient(ftp_socket_addr)

        self._is_ftp_connected = self.ftp_obj.is_connected()
        return_result = True

      except Exception as e:
        return_result = False
        logging.exception(str(e))

      finally:
        return return_result



    def send(self, cmd_kind:config.command_kind, cmd_data) -> config.transaction_capsule:

        if (None == self.cmd_socket):
          cmdret = config.command_return()
          cmdret.errcode = -1
          cmdret.error_lines.append('The TCP connection is not established !!!')
          unknown_capsule = config.transaction_capsule(config.action_kind().response, cmd_kind, cmdret, None)
          return unknown_capsule

        request_capsule = config.transaction_capsule(config.action_kind().request, cmd_kind, data=cmd_data)
        self.cmd_socket.send(request_capsule.toTEXT().encode())

        received = b''
        while True:
            part = self.cmd_socket.recv(self.BUFF_SIZE)
            received = received + part
            if len(part) < self.BUFF_SIZE:
                try:
                    json.loads(str(received, encoding='utf-8'))
                    break
                except Exception as e:
                    continue

        self.cmd_socket.close()

        response_text = str(received, encoding='utf-8')
        resp_data = config.config().toCLASS(response_text)
        return resp_data


    def execute(self, program:str, argument:str=None, work_dirpath:str=None):
        cmd_data = config.execute_command_request_data(self.taskid, program, argument, work_dirpath, False)
        response_capsule = self.send(config.command_kind().execute, cmd_data)
        return response_capsule.result


    def mkdir(self, dirpath:str):
        return self.ftp_obj.try_mkdir(dirpath)


    def upload(self, files:list, dstdir:str):
        return self.ftp_obj.upload(files, dstdir)


    def download(self, files:list, dstdir:str):
        return self.ftp_obj.download(files, dstdir)


    def list(self, files:list, dstdir:str):
        return self.ftp_obj.list(dstdir)


    # def request_puppet_command(self, cmd_kind:config.command_kind, cmd_data):
    #     response_capsule = self.send(cmd_kind, cmd_data)
    #     new_capsulre:config.transaction_capsule = config.transaction_capsule(response_capsule.act_kind,
    #                                                                          response_capsule.cmd_kind,
    #                                                                          response_capsule.result,
    #                                                                          response_capsule.data)
    #     return new_capsulre

