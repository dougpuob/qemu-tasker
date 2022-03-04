# -*- coding: utf-8 -*-
import socket
import json
import logging
from time import sleep
import paramiko
import os
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
from module.sshclient import SSHClient


class client:
    
    
    def __init__(self, host_addr:config.socket_address):
        self.host_addr = host_addr
        self.start_cfg:config.start_config = None

        self.flag_is_ssh_connected = False
        self.conn_tcp = None
        self.conn_ssh = None
        self.conn_sftp = None


    def __del__(self):
        if self.conn_tcp:
            self.conn_tcp.close()
            self.conn_tcp = None

        if self.conn_ssh:
            self.conn_ssh.close()
            self.conn_ssh = None


    def connect_sftp(self, ssh_info:config.ssh_conn_info):
        try:            
            #
            # ssh2-python
            #
            self.conn_ssh = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.conn_ssh:
                self.conn_ssh.connect((ssh_info.host.addr, ssh_info.host.port))
                self.conn_ssh_section = Session()
                self.conn_ssh_section.handshake(self.conn_ssh)
                self.conn_ssh_section.userauth_password(ssh_info.account.username, ssh_info.account.password)
                self.conn_sftp = self.conn_ssh_section.sftp_init()
                self.flag_is_ssh_connected = True

        except Exception as e:
            text = str(e)
            print(text)
            logging.exception(text)


    def send(self, mesg:str) -> str:
        self.conn_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn_tcp.connect((self.host_addr.addr, self.host_addr.port))

        self.conn_tcp.send(mesg.encode())

        BUFF_SIZE = 2048
        received = b''
        while True:
            sleep(0.1)
            part = self.conn_tcp.recv(BUFF_SIZE)
            received = received + part
            if len(part) < BUFF_SIZE:
                try:
                    json.loads(str(received, encoding='utf-8'))
                    break
                except Exception as e:
                    continue

        self.conn_tcp.close()
        return str(received, encoding='utf-8')


    def send_start(self, start_cfg:config.start_config, is_json_report:bool=False):
        self.start_cfg = start_cfg

        start_req = config.start_request(start_cfg.cmd)

        start_req_text = start_req.toTEXT()
        logging.info("● start_req_text={}".format(start_req_text))

        start_resp_text = self.send(start_req_text)
        logging.info("● start_resp_text={}".format(start_resp_text))

        start_resp_data = json.loads(start_resp_text)
        start_r = config.start_reply(start_resp_data['response']['data'])

        if is_json_report:
            print(json.dumps(json.loads(start_resp_text), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] command result: {}".format(start_r.result))


    def send_exec(self, exec_cfg:config.exec_config, is_json_report:bool=False):
        exec_req = config.exec_request(exec_cfg.cmd)
        exec_resp_text = self.send(exec_req.toTEXT())
        logging.info("● exec_resp_text={}".format(exec_resp_text))
        exec_resp_json = json.loads(exec_resp_text)
        exec_resp = config.digest_exec_response(exec_resp_json)
        if is_json_report:
            print(json.dumps(json.loads(exec_resp_text), indent=2, sort_keys=True))
        else:
            for line in exec_resp.reply.stdout:
                print(line)
                logging.info(line)

            for line in exec_resp.reply.stderr:
                print(line)
                logging.info(line)

            print("[qemu-tasker] command result: {}".format(exec_resp.reply.result))


    def send_kill(self, kill_cfg:config.kill_config, is_json_report:bool=False):
        kill_req = config.kill_request(kill_cfg.cmd)
        kill_resp_text = self.send(kill_req.toTEXT())
        logging.info("● kill_resp_text={}".format(kill_resp_text))
        kill_resp_json = json.loads(kill_resp_text)
        kill_resp = config.digest_kill_response(kill_resp_json)

        if is_json_report:
            print(json.dumps(json.loads(kill_resp_text), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] command result: {}".format(kill_resp.reply.result))


    def send_qmp(self, qmp_cfg:config.qmp_config, is_json_report:bool=False):
        qmp_resp = None
        qmp_req = config.qmp_request(qmp_cfg.cmd)
        qmp_resp_text = self.send(qmp_req.toTEXT())

        logging.info("● qmp_resp_text={}".format(qmp_resp_text))
        try:
            qmp_resp = config.digest_qmp_response(json.loads(qmp_resp_text))
        except Exception as e:
            exception_text = "qmp_resp_text={}".format(qmp_resp_text)
            print(exception_text)
            logging.info(exception_text)

            exception_text = "exception={}".format(str(e))
            print(exception_text)
            logging.info(exception_text)

        if is_json_report:
            print(json.dumps(json.loads(qmp_resp_text), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] command result: {}".format(qmp_resp.reply.result))


    def send_file(self, file_cfg:config.file_config, ssh_info:config.ssh_conn_info, is_json_report:bool=False):
        file_resp_text = None
        
        #
        # Target PCs (from)
        #
        pc_from = config.target_kind.unknown        
        sendfrom = file_cfg.cmd.sendfrom.lower()        
        if sendfrom.startswith('s'):
            pc_from = config.target_kind.server
        elif sendfrom.startswith('c'):
            pc_from = config.target_kind.client
        elif sendfrom.startswith('g'):
            pc_from = config.target_kind.guest
        else:
            pass
            
                
        #
        # Target PCs (to)
        #        
        pc_to  = config.target_kind.unknown
        sendto = file_cfg.cmd.sendto.lower()
        if sendto.startswith('s'):
            pc_to = config.target_kind.server
        elif sendto.startswith('c'):
            pc_to = config.target_kind.client
        elif sendto.startswith('g'):
            pc_to = config.target_kind.guest
        else:
            pass
        
        
        #
        # File pathes
        #
        file_from_stat = None
        if os.path.exists(file_cfg.cmd.pathfrom):
            file_from_stat = os.stat(file_cfg.cmd.pathfrom)
        
        
        #
        # client <--> server
        # client <--> guest (direct)
        #
        file_resp = None
        try:
            # client <--> server
            if (pc_from==config.target_kind.client and pc_to==config.target_kind.server) or \
               (pc_from==config.target_kind.server and pc_to==config.target_kind.client):
                   
                logging.info("Transfer file by SFTP (client <--> server)")                
                file_req = config.file_request(file_cfg.cmd)
                file_resp_text = self.send(file_req.toTEXT())
                logging.info("● file_resp_text={}".format(file_resp_text))
                file_resp = config.digest_file_response(json.loads(file_resp_text))

            # client <--> guest (direct)
            elif (pc_from==config.target_kind.client and pc_to==config.target_kind.guest) or \
                 (pc_from==config.target_kind.guest  and pc_to==config.target_kind.client):
                
                # Connect to from client to client.
                self.connect_sftp(ssh_info)
                     
                logging.info("Transfer file by SFTP (client <--> guest (direct))")
                file_reply = config.file_reply(self.send_file_direct(file_cfg))                
                file_resp = config.file_response(file_reply)
                file_resp_json = file_resp.toJSON()
                file_resp_text = file_resp.toTEXT()
                logging.info("● file_resp_text={}".format(file_resp_text))
                file_resp = config.digest_file_response(file_resp_json)
                                
            else:            
                assert(False)
            
            if is_json_report:
                print(json.dumps(json.loads(file_resp_text), indent=2, sort_keys=True))
            else:
                print("[qemu-tasker] command result: {}".format(file_resp.reply.result))

        except Exception as e:
            print("[qemu-tasker] {}".format(e))


    def send_status(self, stat_cfg:config.status_config, is_json_report:bool=False):
        stat_resp = None
        stat_req = config.status_request(stat_cfg.cmd)
        stat_resp_text = self.send(stat_req.toTEXT())

        logging.info("● stat_resp_text={}".format(stat_resp_text))
        try:
            stat_resp = config.digest_qmp_response(json.loads(stat_resp_text))
        except Exception as e:
            exception_text = "stat_resp_text={}".format(stat_resp_text)
            print(exception_text)
            logging.info(exception_text)

            exception_text = "exception={}".format(str(e))
            print(exception_text)
            logging.info(exception_text)

        if is_json_report:
            print(json.dumps(json.loads(stat_resp_text), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] command result: {}".format(stat_resp.reply.result))


    def send_file_direct(self, file_cfg:config.file_config):
        file_from = file_cfg.cmd.pathfrom
        file_to   = file_cfg.cmd.pathto
        
        mode = LIBSSH2_SFTP_S_IRUSR | \
               LIBSSH2_SFTP_S_IWUSR | \
               LIBSSH2_SFTP_S_IRGRP | \
               LIBSSH2_SFTP_S_IROTH
        
        f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
        
        result = False
        errcode = -1
        stderr = ''
        stdout = ''
        
        finfo  = None
        before = datetime.now()
        
        try:
            buf_size = 1024 * 1024
            finfo = os.stat(file_from)
            with open(file_from, 'rb', buf_size) as local_fh, \
                self.conn_sftp.open(file_to, f_flags, mode) as remote_fh:
                data = local_fh.read(buf_size)        
                while data:
                    remote_fh.write(data)
                    data = local_fh.read(buf_size)

            errcode = 0
            result = True
            after = datetime.now() - before
            
        except Exception as e:
            result = False
            stderr = "exception={0}".format(str(e))
            print(stderr)
            logging.info(stderr)

        finally:
            diff = (datetime.now()-before)
            rate = (finfo.st_size / 1024000.0) / diff.total_seconds()            
            stdout = ("Finished writing remote file in {0}, transfer rate {1} MB/s".format(diff, rate))
    
            reply_data = {
                "taskid"  : file_cfg.cmd.taskid,
                "result"  : result,
                "errcode" : errcode,
                "stderr"  : [stderr],
                "stdout"  : [stdout],
            }
            return reply_data
