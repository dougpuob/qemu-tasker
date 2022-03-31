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


# pyftpdlib
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from inspect import currentframe, getframeinfo

from module import config
from module.execproc import execproc
from module.path import OsdpPath



class puppet_server:


    def __init__(self, settings):
        self.BUFF_SIZE = 4096
        self.settings = settings
        self.is_started = False

        # Process
        self.puppet_proc = None
        self.execproc = execproc()

        # TCP
        self.listen_tcp_conn = None
        self.accepted_list:list = []

        # Servers
        self.host_addr:str = self.settings.Puppet.Host.Address
        self.cmd_port:int = self.settings.Puppet.Host.Port.Cmd
        self.ftp_port:int = self.settings.Puppet.Host.Port.Ftp
        self.ftp_user_list:list = []
        for item in self.settings.Puppet.FtpUserList:
            self.ftp_user_list.append(config.account_information(item.UserName, item.Password))


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
        self.start_ftp_server('', self.ftp_port, self.ftp_user_list)



    def start_ftp_server(self, ftp_addr:str, ftp_port:int, account_list:list):

        # Instantiate a dummy authorizer for managing 'virtual' users
        authorizer = DummyAuthorizer()

        # Define a new user having full r/w permissions and a read-only
        # anonymous user
        for item in account_list:
            user_info:config.account_information = item
            homedir = os.path.expanduser('~')
            authorizer.add_user(user_info.username, user_info.password, homedir, perm='elradfmwMT')
        authorizer.add_anonymous(os.getcwd())

        # Instantiate FTP handler class
        handler = FTPHandler
        handler.authorizer = authorizer

        # Define a customized banner (string returned when client connects)
        handler.banner = "qemu-tasker puppet FTP service is ready."

        # Specify a masquerade address and the range of ports to use for
        # passive connections.  Decomment in case you're behind a NAT.
        #handler.masquerade_address = '151.25.42.11'
        #handler.passive_ports = range(60000, 65535)

        # Instantiate FTP server class and listen on 0.0.0.0:2121
        address = ('', ftp_port)
        server = FTPServer(address, handler)

        # set a limit for connections
        server.max_cons = 256
        server.max_cons_per_ip = 5

        # start ftp server
        server.serve_forever()


    def thread_routine_listening_connections(self):
        logging.info("thread_routine_listening_connections ...")
        logging.info("  host_addr={}".format(self.host_addr))
        logging.info("  cmd_port={}".format(self.cmd_port))

        try:
            self.listen_tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listen_tcp_conn.bind((self.host_addr, self.cmd_port))
            self.listen_tcp_conn.listen(10)
            self.is_started = True

            while self.is_started:
                new_conn, new_addr = self.listen_tcp_conn.accept()
                self.accepted_list.append(new_conn)
                thread_for_command = threading.Thread(target = self.thread_routine_processing_command, args=(new_conn,))
                thread_for_command.setDaemon(True)
                thread_for_command.start()

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)


    def thread_routine_processing_command(self, conn:socket.socket):
        logging.info("thread_routine_processing_command ...")

        try:
            incoming_message = str(conn.recv(self.BUFF_SIZE), encoding='utf-8')

            logging.info("conn={}".format(conn))
            logging.info("incomming_message={}".format(incoming_message))

            if incoming_message.startswith("{\"act_kind\": \"request\""):

                cmd_ret = None
                incoming_capsule:config.transaction_capsule = config.config().toCLASS(incoming_message)

                # ------
                # Execute
                # ------
                if config.command_kind().execute == incoming_capsule.cmd_kind:
                    cmd_data:config.execute_command_request_data = incoming_capsule.data
                    cmd_ret = self.handle_execute_command(cmd_data)

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
                    cmd_ret = config.return_unsupported_command()


                return_capsule = config.transaction_capsule(
                                                    config.action_kind().response,
                                                    incoming_capsule.cmd_kind,
                                                    cmd_ret)
                return_capsule_text = return_capsule.toTEXT()
                logging.info("return_capsule_text={}".format(return_capsule_text))
                conn.send(bytes(return_capsule_text, encoding="utf-8"))

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            errmsg = ("exception={0}".format(e)) + '\n' + \
                     ("frameinfo.filename={0}".format(frameinfo.filename)) + '\n' + \
                     ("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(errmsg)


    def handle_execute_command(self, cmd_data:config.execute_command_request_data):
        cmdargs:config.command_argument = config.command_argument(cmd_data.program, cmd_data.argument)
        cmdret = self.execproc.run(cmdargs)
        return cmdret


    def handle_list_command(self, cmd_data:config.list_command_request_data):
        cmdret:config.command_return = config.command_return()
        return cmdret


    def handle_download_command(self, cmd_data:config.download_command_request_data):
        cmdret:config.command_return = config.command_return()
        return cmdret


    def handle_upload_command(self, cmd_data:config.upload_command_request_data):
        cmdret:config.command_return = config.command_return()
        return cmdret


class puppet_client():
    def __init__(self, host_addr:config.socket_address):
        self.BUFF_SIZE = 4096
        self.host_addr = host_addr
        self.cmd_tcp = None

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


    def request_execute_command(self, cmd_data:config.execute_command_request_data):
        response_capsule = self.send(config.command_kind().execute, cmd_data)
        new_capsulre:config.transaction_capsule = config.transaction_capsule(response_capsule.act_kind,
                                                                             response_capsule.cmd_kind,
                                                                             response_capsule.result,
                                                                             response_capsule.data)
        return new_capsulre
