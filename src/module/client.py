# -*- coding: utf-8 -*-
import os
import json
import socket
import logging

from time import sleep
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
from module.sshclient import ssh_link


class client:
    
    
    def __init__(self, host_addr:config.socket_address):
        self.host_addr = host_addr
        self.start_cfg:config.start_config = None

        self.flag_is_ssh_connected = False
        self.ssh_link = None


    def __del__(self):
        pass


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


    def list_file(self, list_cfg:config.list_config, is_json_report:bool=False):
      
        stat_resp = None
        stat_cmd = config.status_command(list_cfg.cmd.taskid)
        stat_req = config.status_request(stat_cmd)
        stat_resp_text = self.send(stat_req.toTEXT())
        stat_resp = config.digest_status_response(json.loads(stat_resp_text))
      
        try:
            mysshlink = ssh_link()            
            is_connected = mysshlink.connect(stat_resp.reply.ssh_info.targetaddr,
                                             stat_resp.reply.ssh_info.targetport,
                                             stat_resp.reply.ssh_info.username,
                                             stat_resp.reply.ssh_info.password)            
      
            cmdret = config.cmd_return()      
            if is_connected:                
                dirpath = list_cfg.cmd.dirpath
                cmdret = mysshlink.readdir(dirpath)
            
            reply_data = {
                "taskid"  : list_cfg.cmd.taskid,
                "result"  : (0 == cmdret.errcode),
                "errcode" : cmdret.errcode,
                "stderr"  : cmdret.error_lines,
                "stdout"  : cmdret.info_lines,
                "readdir" : cmdret.data,
            }

            list_reply = config.list_reply(reply_data)
            list_resp = config.list_response(list_reply)
            list_resp_text = list_resp.toTEXT()
            logging.info("● file_resp_text={}".format(list_resp_text))
            if is_json_report:
                print(json.dumps(json.loads(list_resp_text), indent=2, sort_keys=True))
            else:
                print("[qemu-tasker] command result: {}".format(list_resp_text.reply.result))

        except Exception as e:
            text = str(e)
            print(text)
            print("[qemu-tasker] {}".format(text))


    def download_file(self, download_cfg:config.download_config, is_json_report:bool=False):
      
        stat_resp = None
        stat_cmd = config.status_command(download_cfg.cmd.taskid)
        stat_req = config.status_request(stat_cmd)
        stat_resp_text = self.send(stat_req.toTEXT())
        stat_resp = config.digest_status_response(json.loads(stat_resp_text))
      
        cmdret = config.cmd_return()
        file_resp = None
        
        try:
            mysshlink = ssh_link()            
            is_connected = mysshlink.connect(stat_resp.reply.ssh_info.targetaddr,
                                             stat_resp.reply.ssh_info.targetport,
                                             stat_resp.reply.ssh_info.username,
                                             stat_resp.reply.ssh_info.password)            
            final_cmdret = config.cmd_return()
            
            is_path_there = False

            if is_connected:                
                dirpath = download_cfg.cmd.dirpath
                retcmd = mysshlink.mkdir(dirpath)
                is_path_there = (0 == retcmd.errcode)
                final_cmdret.info_lines.extend(retcmd.info_lines)
            
            if is_connected and is_path_there:
                for file_path in download_cfg.cmd.files:
                    basename = os.path.basename(file_path)
                    target_path = os.path.join(download_cfg.cmd.dirpath, basename)
                    
                    cmdret = mysshlink.download(file_path, target_path)
                                        
                    final_cmdret.errcode = cmdret.errcode                    
                    final_cmdret.info_lines.append('--------------------------------------------------')                    
                    final_cmdret.info_lines.extend(cmdret.info_lines)                    
                    final_cmdret.error_lines.append('--------------------------------------------------')
                    final_cmdret.error_lines.extend(cmdret.error_lines)
                                        
                    if cmdret.errcode != 0:
                        break
            
            reply_data = {
                "taskid"  : download_cfg.cmd.taskid,
                "result"  : (0 == cmdret.errcode),
                "errcode" : final_cmdret.errcode,
                "stderr"  : final_cmdret.error_lines,
                "stdout"  : final_cmdret.info_lines,
            }

            dload_reply = config.download_reply(reply_data)
            dload_resp = config.download_response(dload_reply)
            dload_resp_text = dload_resp.toTEXT()
            logging.info("● file_resp_text={}".format(dload_resp_text))
            if is_json_report:
                print(json.dumps(json.loads(dload_resp_text), indent=2, sort_keys=True))
            else:
                print("[qemu-tasker] command result: {}".format(dload_resp_text.reply.result))

        except Exception as e:
            text = str(e)
            print(text)
            print("[qemu-tasker] {}".format(text))

    def upload_file(self, upload_cfg:config.upload_config, is_json_report:bool=False):
          
        stat_resp = None
        stat_cmd = config.status_command(upload_cfg.cmd.taskid)
        stat_req = config.status_request(stat_cmd)
        stat_resp_text = self.send(stat_req.toTEXT())
        stat_resp = config.digest_status_response(json.loads(stat_resp_text))
      
        cmdret = config.cmd_return()
        file_resp = None
        
        try:
            mysshlink = ssh_link()            
            is_connected = mysshlink.connect(stat_resp.reply.ssh_info.targetaddr,
                                             stat_resp.reply.ssh_info.targetport,
                                             stat_resp.reply.ssh_info.username,
                                             stat_resp.reply.ssh_info.password)
            final_cmdret = config.cmd_return()
            
            is_path_there = False

            if is_connected:
                dirpath = upload_cfg.cmd.dirpath
                retcmd = mysshlink.mkdir(dirpath)
                is_path_there = (0 == retcmd.errcode)
                final_cmdret.info_lines.extend(retcmd.info_lines)
            
            if is_connected and is_path_there:                
                for file_path in upload_cfg.cmd.files:
                    basename = os.path.basename(file_path)
                    target_path = os.path.join(upload_cfg.cmd.dirpath, basename)
                    
                    cmdret = mysshlink.upload(file_path, target_path)
                                        
                    final_cmdret.errcode = cmdret.errcode                    
                    final_cmdret.info_lines.append('--------------------------------------------------')                    
                    final_cmdret.info_lines.extend(cmdret.info_lines)                    
                    final_cmdret.error_lines.append('--------------------------------------------------')
                    final_cmdret.error_lines.extend(cmdret.error_lines)
                                        
                    if cmdret.errcode != 0:
                        break
            
            reply_data = {
                "taskid"  : upload_cfg.cmd.taskid,
                "result"  : (0 == cmdret.errcode),
                "errcode" : final_cmdret.errcode,
                "stderr"  : final_cmdret.error_lines,
                "stdout"  : final_cmdret.info_lines,
            }

            dload_reply = config.upload_reply(reply_data)
            dload_resp = config.upload_response(dload_reply)
            dload_resp_text = dload_resp.toTEXT()
            logging.info("● file_resp_text={}".format(dload_resp_text))
            if is_json_report:
                print(json.dumps(json.loads(dload_resp_text), indent=2, sort_keys=True))
            else:
                print("[qemu-tasker] command result: {}".format(dload_resp_text.reply.result))

        except Exception as e:
            text = str(e)
            print(text)
            print("[qemu-tasker] {}".format(text))


    def send_push(self, push_cfg:config.push_config, is_json_report:bool=False):
        push_resp = None
        push_req = config.push_request(push_cfg.cmd)
        push_resp_text = self.send(push_req.toTEXT())

        logging.info("● push_resp_text={}".format(push_resp_text))
        try:
            qmp_resp = config.digest_push_response(json.loads(push_resp_text))
        except Exception as e:
            exception_text = "push_resp_text={}".format(push_resp_text)
            print(exception_text)
            logging.info(exception_text)

            exception_text = "exception={}".format(str(e))
            print(exception_text)
            logging.info(exception_text)

        if is_json_report:
            print(json.dumps(json.loads(push_resp_text), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] command result: {}".format(qmp_resp.reply.result))


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
