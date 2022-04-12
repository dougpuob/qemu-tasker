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


    def __init__(self, taskid:int, word_dir:str=None):
      self.BUFF_SIZE = 4096
      self.taskid = taskid
      self.cmd_socket = None
      self.ftp_obj = None
      self._is_cmd_connected = False
      self._is_ftp_connected = False
      self.WORK_DIR = word_dir


    def __del__(self):

      if self.cmd_socket:
        self.disconnect()
        self.cmd_socket.close()

      if self.ftp_obj:
        self.ftp_obj.close()


    def is_cmd_connected(self):
        return self._is_cmd_connected


    def is_ftp_connected(self):
        return self._is_ftp_connected


    def connect_cmd(self, cmd_socket_addr:config.socket_address):
      result:bool = False

      try:
        #logging.info("puppet client is trying to connect command socket ... (addr={0} port={1})".format(cmd_socket_addr.address, cmd_socket_addr.port))
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ret = self.cmd_socket.connect_ex((cmd_socket_addr.address, cmd_socket_addr.port))

        if ret:
          result = False
          self._is_cmd_connected = False
        else:
          result = True
          self._is_cmd_connected = True

      except Exception as e:
        result = False
        logging.exception(str(e))

      finally:
        return result


    def connect_ftp(self,
                ftp_socket_addr:config.socket_address,
                ftp_user_info:config.account_information=None):

      try:
        if ftp_user_info:
          #logging.info("puppet client is trying to connect FTP socket (username & password) ... (addr={0} port={1})".format(ftp_socket_addr.address, ftp_socket_addr.port))
          self.ftp_obj = ftpclient(ftp_socket_addr, ftp_user_info)
          if self.ftp_obj:
            self.ftp_obj.connect()
        else:
          # anonymous
          logging.info("puppet client is trying to connect FTP socket (anonymous)  ... (addr={0} port={1})".format(ftp_socket_addr.address, ftp_socket_addr.port))
          self.ftp_obj = ftpclient(ftp_socket_addr)
          if self.ftp_obj:
            ret = self.ftp_obj.connect()
            if ret and self.WORK_DIR:

              cmd_ret = self.ftp_obj.try_mkdir(self.WORK_DIR)
              logging.info("self.ftp_obj.try_mkdir() cmd_ret={}".format(cmd_ret))

              cmd_ret = self.ftp_obj.cd(self.WORK_DIR)
              logging.info("self.ftp_obj.cd() cmd_ret={}".format(cmd_ret))

        if self.ftp_obj:
          self._is_ftp_connected = self.ftp_obj.is_connected()

      except Exception as e:
        self._is_ftp_connected = False
        logging.exception(str(e))

      finally:
        return self._is_ftp_connected


    def send_request(self, cmd_kind:config.command_kind, cmd_data):

      if cmd_kind == config.command_kind().execute:
        return self.send_to_governor_server(cmd_kind, cmd_data)

      elif cmd_kind == config.command_kind().list or \
           cmd_kind == config.command_kind().download or \
           cmd_kind == config.command_kind().upload or \
           cmd_kind == config.command_kind().breakup:
        return self.send_to_puppet_server(cmd_kind, cmd_data)

      else:
        assert 'Handle this wrong case !!!'


    def send_to_puppet_server(self, cmd_kind:config.command_kind, cmd_data):
      cmd_ret = None

      if cmd_kind == config.command_kind().list:
        new_cmd_data:config.list_command_request_data = cmd_data
        cmd_ret = self.list(new_cmd_data.dstdir)

      elif cmd_kind == config.command_kind().download:
        new_cmd_data:config.download_command_request_data = cmd_data
        cmd_ret = self.download(new_cmd_data.files, new_cmd_data.dstdir)

      elif cmd_kind == config.command_kind().upload:
        new_cmd_data:config.upload_command_request_data = cmd_data
        cmd_ret = self.upload(new_cmd_data.files, new_cmd_data.dstdir)

      elif cmd_kind == config.command_kind().breakup:
        cmd_ret = self.disconnect()

      else:
        cmd_ret = config.return_command_unsupported

      # Tidy cmd_ret.data because it will be returned from another field.
      cmd_ret_data = cmd_ret.data
      cmd_ret.data = None

      resp_capsule = config.transaction_capsule(config.action_kind().response,
                                                cmd_kind,
                                                cmd_ret,
                                                cmd_ret_data)
      return resp_capsule


    def send_to_governor_server(self, cmd_kind:config.command_kind, cmd_data):

      #
      # Check conditions
      #
      assert self.cmd_socket, 'self.cmd_socket is None !!!'
      assert self.is_cmd_connected, 'self.is_cmd_connected is FALSE !!!'

      if None == self.cmd_socket:
        logging.error('self.cmd_socket is None !!!')
        cmdret = config.command_return()
        cmdret.errcode = -1
        cmdret.error_lines.append('The TCP connection is not established !!!')
        unknown_capsule = config.transaction_capsule(config.action_kind().response, cmd_kind, cmdret, None)
        return unknown_capsule

      #
      # Send request to governor server
      #
      cmd_ret = None
      if cmd_kind == config.command_kind().execute:

        request_capsule = config.transaction_capsule(config.action_kind().request, cmd_kind, data=cmd_data)
        self.cmd_socket.send(request_capsule.toTEXT().encode())

        received = b''
        while True:
          time.sleep(1)
          part = self.cmd_socket.recv(self.BUFF_SIZE)
          received = received + part
          if len(part) < self.BUFF_SIZE:
              try:
                  json.loads(str(received, encoding='utf-8'))
                  break
              except Exception as e:
                  continue

        response_text = str(received, encoding='utf-8')
        resp_data = config.config().toCLASS(response_text)
        cmd_ret = resp_data.result

      else:
        cmd_ret = config.return_command_unsupported

      # Tidy cmd_ret.data because it will be returned from another field.
      cmd_ret_data = cmd_ret.data
      cmd_ret.data = None

      resp_capsule = config.transaction_capsule(config.action_kind().response,
                                                cmd_kind,
                                                cmd_ret,
                                                cmd_ret_data)
      return resp_capsule


    def disconnect(self):
      cmd_data = config.generic_command_request_data(self.taskid)
      response_capsule = self.send_to_governor_server(config.command_kind().breakup, cmd_data)
      return response_capsule.result


    def execute(self, program:str, argument:str=None, work_dirpath:str=None):
      cmd_data = config.execute_command_request_data(self.taskid, program, argument, work_dirpath, False)
      response_capsule = self.send_to_governor_server(config.command_kind().execute, cmd_data)
      return response_capsule.result


    def mkdir(self, dirpath:str):
      return self.ftp_obj.try_mkdir(dirpath)


    # def cd(self, dirpath:str):
    #   return self.ftp_obj.cd(dirpath)


    def upload(self, files:list, dstdir:str):
      return self.ftp_obj.upload(files, dstdir)


    def download(self, files:list, dstdir:str):
      return self.ftp_obj.download(files, dstdir)


    def list(self, dstdir:str):
      return self.ftp_obj.list(dstdir)
