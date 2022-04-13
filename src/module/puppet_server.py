# -*- coding: utf-8 -*-
from collections import UserList
import os
import json
from pickle import NONE
import time
import socket
import logging
import threading
import select
import subprocess

# pyftpdlib
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from inspect import currentframe, getframeinfo

from module import config
from module.execproc import execproc
from module.path import OsdpPath
from module.ftpclient import ftpclient



# =================================================================================================
#
# =================================================================================================
class puppet_server_base():
  def __init__(self):
    pass


# =================================================================================================
#
# =================================================================================================
class puppet_server_mock(puppet_server_base):
  def __init__(self):
    pass


# =================================================================================================
#
# =================================================================================================
class puppet_server(puppet_server_base):

    def __init__(self, setting):
        self.BUFF_SIZE = 4096
        self.setting = setting
        self.is_started = False

        # Process
        self.puppet_proc = None
        self.execproc = execproc()
        self.client = None

        # TCP
        self.listen_tcp_conn = None
        self.accepted_list:list = []

        # Servers
        self.cmd_host = config.socket_address(self.setting.Puppet.Address, self.setting.Puppet.Port.Cmd)
        self.ftp_server_addr_info = config.socket_address(self.setting.Puppet.Address, self.setting.Puppet.Port.Ftp)


    def __del__(self):
        if self.listen_tcp_conn:
            self.listen_tcp_conn.close()
            self.listen_tcp_conn = None

        if self.thread_tcp:
            self.thread_tcp = None

        if self.accepted_list:
            for item in self.accepted_list:
                if item:
                    item.close()
            self.accepted_list.clear()


    def start(self):

        #
        # Wait connections and commands from clients.
        #
        self.thread_tcp = threading.Thread(target = self.thread_routine_listening_connections)
        self.thread_tcp.setDaemon(True)
        self.thread_tcp.start()


        #
        # Start FTP server
        #
        self.start_ftp_server(self.ftp_server_addr_info)



    def start_ftp_server(self, ftp_host:config.socket_address):
        ftp_homedir  = os.path.expanduser('~')

        authorizer = DummyAuthorizer()
        #authorizer.add_user(ftp_username, ftp_password, ftp_homedir, perm='elradfmwMT')
        authorizer.add_anonymous(ftp_homedir, perm='elradfmwMT')

        handler = FTPHandler
        handler.authorizer = authorizer

        ftp_server = FTPServer(('0.0.0.0', ftp_host.port), handler)

        # set a limit for connections
        ftp_server.max_cons = 256
        ftp_server.max_cons_per_ip = 10

        # 60*60*24 = 86400(24Hours)
        ftp_server.serve_forever(timeout=86400)


    def thread_routine_listening_connections(self):
        logging.info("thread_routine_listening_connections ...")
        logging.info("  self.cmd_host.address={}".format(self.cmd_host.address))
        logging.info("  self.cmd_host.port   ={}".format(self.cmd_host.port))

        try:
            self.listen_tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.listen_tcp_conn:
                self.listen_tcp_conn.bind(('0.0.0.0', self.cmd_host.port))
                self.listen_tcp_conn.listen(10)
                self.is_started = True

            while self.is_started:
                logging.info("puppet server is waiting for connection ...")
                new_conn, new_addr = self.listen_tcp_conn.accept()
                logging.info("puppet server accepted a new connection ... (new_addr={})".format(new_addr))
                #self.accepted_list.append(new_conn)
                thread_handling_commands = threading.Thread(target = self.thread_routine_processing_command, args=(new_conn,))
                thread_handling_commands.setDaemon(True)
                thread_handling_commands.start()

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)


    def thread_routine_processing_command(self, new_conn):
        logging.info("thread_routine_processing_command ...")

        logging.info("new_conn={}".format(new_conn))
        _keep_going = True

        try:

            received = b''
            while _keep_going:

                part = new_conn.recv(self.BUFF_SIZE)
                received = received + part
                if len(part) > 0:
                    continue

                time.sleep(1)
                incoming_message = ''
                try:
                    incoming_message = str(received, encoding='utf-8')
                except Exception as e:
                    received = b''
                    logging.exception("incoming_message={}".format(incoming_message))
                    continue

                logging.info("incoming_message={}".format(incoming_message))

                if not incoming_message.startswith("{\"act_kind\": \"request\""):
                    logging.info("Received an unknow message !!! (len(incoming_message)={})".format(len(incoming_message)))
                    logging.info("{}".format(incoming_message))

                else:
                    cmd_ret = None
                    incoming_capsule:config.transaction_capsule = config.config().toCLASS(incoming_message)

                    # ------
                    # Breakup
                    # ------
                    if config.command_kind().breakup == incoming_capsule.cmd_kind:
                        _keep_going = False
                        cmd_ret = config.command_return()

                    # ------
                    # Execute
                    # ------
                    elif config.command_kind().execute == incoming_capsule.cmd_kind:
                        cmd_data:config.execute_command_request_data = incoming_capsule.data
                        logging.info("self.handle_execute_command(cmd_data) 1")
                        cmd_ret = self.handle_execute_command(cmd_data)
                        logging.info("self.handle_execute_command(cmd_data) 2")

                    # ------
                    # List
                    # ------
                    elif config.command_kind().list == incoming_capsule.cmd_kind:
                        cmd_data:config.list_command_request_data = incoming_capsule.data
                        cmd_ret = self.handle_list_command(cmd_data)

                    # ------
                    # Download
                    # ------
                    elif config.command_kind().download == incoming_capsule.cmd_kind:
                        cmd_data:config.download_command_request_data = incoming_capsule.data
                        cmd_ret = self.handle_download_command(cmd_data)

                    # ------
                    # Upload
                    # ------
                    elif config.command_kind().upload == incoming_capsule.cmd_kind:
                        cmd_data:config.upload_command_request_data = incoming_capsule.data
                        cmd_ret = self.handle_upload_command(cmd_data)

                    # ------
                    # Unsupported commands
                    # ------
                    else:
                        cmd_ret = config.return_command_unsupported


                    return_capsule = config.transaction_capsule(
                                                        config.action_kind().response,
                                                        incoming_capsule.cmd_kind,
                                                        cmd_ret)
                    return_capsule_text = return_capsule.toTEXT()
                    logging.info("return_capsule_text={}".format(return_capsule_text))
                    new_conn.send(bytes(return_capsule_text, encoding="utf-8"))
                    received = b''

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            logging.exception("exception={0}".format(e))
            logging.exception("frameinfo.filename={0}".format(frameinfo.filename))
            logging.exception("frameinfo.lineno={0}".format(frameinfo.lineno))


    def handle_execute_command(self, cmd_data:config.execute_command_request_data):
        cmdargs:config.command_argument = config.command_argument(cmd_data.program, cmd_data.argument)
        cmdret = self.execproc.run(cmdargs, cmd_data.workdir, cmd_data.is_base64)
        return cmdret


    def handle_list_command(self, cmd_data:config.list_command_request_data):
        if self.client == None:
            self.client = ftpclient(self.ftp_server_addr_info)
        cmdret = self.client.list(cmd_data.dstdir)
        return cmdret


    def handle_download_command(self, cmd_data:config.download_command_request_data):
        if self.client == None:
            self.client = ftpclient(self.ftp_server_addr_info)
        cmdret = self.client.download(cmd_data.files, cmd_data.dstdir)
        return cmdret


    def handle_upload_command(self, cmd_data:config.upload_command_request_data):
        if self.client == None:
            self.client = ftpclient(self.ftp_server_addr_info)
        cmdret = self.client.upload(cmd_data.files, cmd_data.dstdir)
        return cmdret

