# -*- coding: utf-8 -*-
import socket
import json

from module import config


class client:
    def __init__(self, socket_addr:config.socket_address):
        self.socket_addr = socket_addr
        self.task_info_list_ = []
        self.tcp_conn = None

    def __del__(self):
        if self.tcp_conn:
            self.tcp_conn.close()
            self.tcp_conn = None

    def send(self, mesg:str) -> str:
        self.tcp_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_conn.connect((self.socket_addr.addr, self.socket_addr.port))
        
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
        start_req = config.start_request(start_cfg.cmd)

        start_req_text = start_req.toTEXT()        
        print("{}● start_req_text={}".format("", start_req_text))

        start_resp_text = self.send(start_req_text)
        print("{}● start_resp_text={}".format("", start_resp_text))

        start_resp_data = json.loads(start_resp_text)
        start_r = config.start_reply(start_resp_data['response']['data'])
                
    def send_exec(self, exec_cfg:config.exec_config):
        exec_req = config.exec_request(exec_cfg.cmd)
        exec_resp_text = self.send(exec_req.toTEXT())
        print("{}● exec_resp_text={}".format("", exec_resp_text))
        exec_resp = config.digest_exec_response(json.loads(exec_resp_text))
        
    def send_kill(self, kill_cfg:config.kill_config):
        kill_req = config.kill_request(kill_cfg.cmd)
        kill_resp_text = self.send(kill_req.toTEXT())                        
        print("{}● kill_resp_text={}".format("", kill_resp_text))
        kill_resp_json = json.loads(kill_resp_text)
        kill_resp = config.digest_kill_response(kill_resp_json)

    def send_qmp(self, qmp_cfg:config.qmp_config):
        qmp_req = config.qmp_request(qmp_cfg.cmd)
        qmp_resp_text = self.send(qmp_req.toTEXT())
        print("{}● qmp_resp_text={}".format("", qmp_resp_text))
        qmp_resp = config.digest_qmp_response(json.loads(qmp_resp_text))    
