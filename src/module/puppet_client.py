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

from module.pyrc.rc import rcclient
from module.pyrc.rc import rcresult
from module import config

# =================================================================================================
#
# =================================================================================================
class puppet_client():


    def __init__(self, taskid:int, word_dir:str=None):

      self.BUFF_SIZE = 4096
      self.taskid = taskid
      self.cmd_socket = None
      self._is_connected = False
      self.WORK_DIR = word_dir

      self.pyrc_client = rcclient()


    def __del__(self):

      if self.cmd_socket:
        self.disconnect()
        self.cmd_socket.close()


    def is_connected(self):
        return self.pyrc_client.is_connected()


    def connect(self, cmd_socket_addr:config.socket_address):

      try:
        logging.info("puppet client is trying to connect command socket ... (addr={0} port={1})".format(cmd_socket_addr.address, cmd_socket_addr.port))
        self._is_connected = self.pyrc_client.connect(cmd_socket_addr.address,
                                                      cmd_socket_addr.port)

        if self._is_connected:
          logging.error("failed to connect to command channel !!!")
        else:
          logging.info("connected to command channel !!!")

      except Exception as e:
        self._is_connected = False
        logging.exception('Failed to connect to command socket !!!')

      finally:
        return self._is_connected


    def disconnect(self):
      cmd_data = config.generic_command_request_data(self.taskid)
      response_capsule = self.handle_cmd_request(config.command_kind().breakup, cmd_data)
      return response_capsule.result


    def execute(self, program:str, argument:str='', workdir:str=''):
      result: rcresult = self.pyrc_client.execute(program, argument, workdir)
      return result.data


    def mkdir(self, dirpath:str):
      result: rcresult = self.pyrc_client.execute('mkdir', dirpath)
      return (0 == result.errcode)


    def upload(self, files:list, dstdir:str):
      ret = True
      for file in files:
        result: rcresult = self.pyrc_client.upload(file, dstdir)
        if (0 == result.errcode):
          logging.info('Passed to upload "{}" file.', file)
        else:
          logging.error('Failed to upload "{}" file.', file)
          ret = False
      return ret


    def download(self, files:list, dstdir:str):
      ret = True
      for file in files:
        result: rcresult = self.pyrc_client.download(file, dstdir)
        if (0 == result.errcode):
          logging.info('Passed to download "{}" file.', file)
        else:
          logging.error('Failed to download "{}" file.', file)
          ret = False
      return ret


    def list(self, dstdir:str):
      result: rcresult = self.pyrc_client.list(dstdir)
      return result.data

