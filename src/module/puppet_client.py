# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-
from collections import UserList
import os
import json
from pickle import NONE
import time
import socket
import logging
import threading
import subprocess


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

    def send(self, cmd_kind:config.command_kind, cmd_data) -> config.transaction_capsule:
        request_capsule = config.transaction_capsule(config.action_kind().request, cmd_kind, data=cmd_data)

        self.cmd_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_tcp.connect((self.host_addr.address, self.host_addr.port))
        self.cmd_tcp.send(request_capsule.toTEXT().encode())

        received = b''
        while True:
            part = self.cmd_tcp.recv(self.BUFF_SIZE)
            received = received + part
            if len(part) < self.BUFF_SIZE:
                try:
                    json.loads(str(received, encoding='utf-8'))
                    break
                except Exception as e:
                    continue

        self.cmd_tcp.close()

        response_text = str(received, encoding='utf-8')
        resp_data = config.config().toCLASS(response_text)
        return resp_data


    def request_puppet_command(self, cmd_kind:config.command_kind, cmd_data:config.execute_command_request_data):
        response_capsule = self.send(cmd_kind, cmd_data)
        new_capsulre:config.transaction_capsule = config.transaction_capsule(response_capsule.act_kind,
                                                                             response_capsule.cmd_kind,
                                                                             response_capsule.result,
                                                                             response_capsule.data)
        return new_capsulre

