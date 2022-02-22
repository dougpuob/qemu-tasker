# -*- coding: utf-8 -*-
import socket
import json
import logging
import paramiko

from module import config


class client:
    def __init__(self, host_addr:config.socket_address):
        self.host_addr = host_addr        
        self.start_cfg:config.start_config = None

        self.flag_is_ssh_connected = False
        self.tcp_conn = None
        self.ssh_conn = None

    def __del__(self):
        if self.tcp_conn:
            self.tcp_conn.close()
            self.tcp_conn = None

        if self.ssh_conn:
            self.ssh_conn.close()
            self.ssh_conn = None

    def connect_sftp(self):
        self.conn_sftp = paramiko.SSHClient()
        self.conn_sftp.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.conn_sftp.connect(self.host_addr.addr,
                                self.host_addr.port, 
                                self.start_cfg.cmd.ssh_login.username,
                                self.start_cfg.cmd.ssh_login.password,
                                banner_timeout=200,
                                timeout=200)
            self.flag_is_ssh_connected = True

        except Exception as e:
            print(e)
            logging.exception(e)
        

    def send(self, mesg:str) -> str:
        self.tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_conn.connect((self.host_addr.addr, self.host_addr.port))
        
        self.tcp_conn.send(mesg.encode())
        
        BUFF_SIZE = 2048
        received = b''
        while True:            
            part = self.tcp_conn.recv(BUFF_SIZE)
            received = received + part
            if len(part) < BUFF_SIZE:
                break
                
        self.tcp_conn.close()
        return str(received, encoding='utf-8')

    def send_start(self, start_cfg:config.start_config):
        self.start_cfg = start_cfg

        start_req = config.start_request(start_cfg.cmd)

        start_req_text = start_req.toTEXT()               
        logging.info("● start_req_text={}".format(start_req_text))

        start_resp_text = self.send(start_req_text)
        logging.info("● start_resp_text={}".format(start_resp_text))

        start_resp_data = json.loads(start_resp_text)
        start_r = config.start_reply(start_resp_data['response']['data'])
        print("[qemu-tasker] command result: {}".format(start_r.result))
        if start_r.result:
            print("TaskId  : {}".format(start_r.taskid))
            print("FwPorts : {}".format(start_r.fwd_ports.toJSON()))
            logging.info("TaskId  : {}".format(start_r.taskid))
            logging.info("FwPorts : {}".format(start_r.fwd_ports.toJSON()))
                        
    def send_exec(self, exec_cfg:config.exec_config):
        exec_req = config.exec_request(exec_cfg.cmd)
        exec_resp_text = self.send(exec_req.toTEXT())
        logging.info("● exec_resp_text={}".format(exec_resp_text))
        exec_resp = config.digest_exec_response(json.loads(exec_resp_text))
        print("[qemu-tasker] command result: {}".format(exec_resp.reply.result))
        for line in exec_resp.reply.stdout:
            print(line)
            logging.info(line)
        for line in exec_resp.reply.stderr:
            print(line)
            logging.info(line)
        
    def send_kill(self, kill_cfg:config.kill_config):
        kill_req = config.kill_request(kill_cfg.cmd)
        kill_resp_text = self.send(kill_req.toTEXT())                        
        logging.info("● kill_resp_text={}".format(kill_resp_text))
        kill_resp_json = json.loads(kill_resp_text)
        kill_resp = config.digest_kill_response(kill_resp_json)
        print("[qemu-tasker] command result: {}".format(kill_resp.reply.result))

    def send_qmp(self, qmp_cfg:config.qmp_config):
        qmp_req = config.qmp_request(qmp_cfg.cmd)
        qmp_resp_text = self.send(qmp_req.toTEXT())
        logging.info("● qmp_resp_text={}".format(qmp_resp_text))
        qmp_resp = config.digest_qmp_response(json.loads(qmp_resp_text))    
        print("[qemu-tasker] command result: {}".format(qmp_resp.reply.result))
        
    def send_file(self, file_cfg:config.file_config):
        file_req = config.file_request(file_cfg.cmd)
        file_resp_text = self.send(file_req.toTEXT())
        logging.info("● file_resp_text={}".format(file_resp_text))
        try:
            file_resp = config.digest_file_response(json.loads(file_resp_text))    
            print("[qemu-tasker] command result: {}".format(file_resp.reply.result))
            if not file_resp.reply.result:
                print("stdout :{}".format(file_resp.reply.stdout))
                print("stderr :{}".format(file_resp.reply.stderr))
                print("errcode:{}".format(file_resp.reply.errcode))
            
        except Exception as e:            
            print("[qemu-tasker] {}".format(e))
        