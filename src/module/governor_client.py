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
# Internal modules
#
from module import config
from module.path import OsdpPath




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


    def send_control_command(self, cmd_kind:config.command_kind, cmd_data, is_json_report:bool):
        return self.mock_return_data


# =================================================================================================
#
# =================================================================================================
class governor_client(governor_client_base):

    def __init__(self, host_addr:config.socket_address):
        self.BUFF_SIZE = 4096

        self.path = OsdpPath()
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

        resp_capsule = config.config().toCLASS(response_text)
        new_resp_capsule = config.transaction_capsule(resp_capsule.act_kind,
                                                      resp_capsule.cmd_kind,
                                                      resp_capsule.result,
                                                      resp_capsule.data)
        return new_resp_capsule
