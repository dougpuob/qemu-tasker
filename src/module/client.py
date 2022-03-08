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


    def send_file(self, file_cfg:config.file_config, ssh_info:config.ssh_conn_info, is_json_report:bool=False):
        file_resp_text = None
        
        #
        # Target PCs
        #
        pc_from = file_cfg.cmd.sendfrom 
        pc_to  = file_cfg.cmd.sendto
        
        #
        # Local <--> Server
        # Local <--> Guest (direct)
        #
        cmdret = config.cmd_return()
        file_resp = None
        try:
            # Local <--> Server (Request by the `file` command)
            if (pc_from==config.target_kind.local  and pc_to==config.target_kind.server) or \
               (pc_from==config.target_kind.server and pc_to==config.target_kind.local):
                   
                logging.info("Transfer file by TCP (Local <--> Server)")
                file_req = config.file_request(file_cfg.cmd)
                file_resp_text = self.send(file_req.toTEXT())
                self.conn_tcp.recvfrom()
                logging.info("● file_resp_text={}".format(file_resp_text))
                file_resp = config.digest_file_response(json.loads(file_resp_text))

            # Local <--> Guest (Connect directly)
            elif pc_from==config.target_kind.local and pc_to==config.target_kind.guest or \
                 pc_from==config.target_kind.guest and pc_to==config.target_kind.local:
                
                logging.info("Transfer file by SFTP (Local <--> Guest)")
                
                link_ssh = ssh_link()
                is_connected = self.link_ssh.connect(ssh_info.host.addr,
                                                     ssh_info.host.port,
                                                     ssh_info.account.username,
                                                     ssh_info.account.password)                
                if is_connected:
                    # upload
                    if pc_from==config.target_kind.local and pc_to==config.target_kind.guest:
                        cmdret = self.ssh_link.upload(file_cfg.cmd.pathfrom, file_cfg.cmd.pathto)
                    
                    # download
                    elif pc_from==config.target_kind.guest and pc_to==config.target_kind.local:
                        cmdret = self.ssh_link.download(file_cfg.cmd.pathfrom, file_cfg.cmd.pathto)
                    
                reply_data = {
                    "taskid"  : file_cfg.cmd.taskid,
                    "result"  : (0 == cmdret.errcode),
                    "errcode" : cmdret.errcode,
                    "stderr"  : cmdret.error_lines,
                    "stdout"  : cmdret.info_lines,
                }

                file_reply = config.file_reply(reply_data)
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
            text = str(e)
            print(text)
            print("[qemu-tasker] {}".format(text))


    # def transfer_file(self, tfx_ind:config.transfer_kind, download_cfg:config.download_config, is_json_report:bool=False):
      
    #     stat_resp = None
    #     stat_cmd = config.status_command(download_cfg.cmd.taskid)
    #     stat_req = config.status_request(stat_cmd)
    #     stat_resp_text = self.send(stat_req.toTEXT())
    #     stat_resp = config.digest_status_response(json.loads(stat_resp_text))
      
    #     cmdret = config.cmd_return()
    #     file_resp = None
        
    #     try:
    #         mysshlink = ssh_link()            
    #         is_connected = mysshlink.connect(stat_resp.reply.ssh_info.targetaddr,
    #                                          stat_resp.reply.ssh_info.targetport,
    #                                          stat_resp.reply.ssh_info.username,
    #                                          stat_resp.reply.ssh_info.password)   
    #         final_cmdret = config.cmd_return()
            
    #         is_path_there = False
    #         if is_connected:                
    #             dirpath = download_cfg.cmd.saveto
    #             retcmd = mysshlink.mkdir(dirpath)
    #             is_path_there = (0 == retcmd.errcode)
    #             final_cmdret.info_lines.extend(retcmd.info_lines)
            
    #         if is_connected and is_path_there:                
    #             for file_path in download_cfg.cmd.files:
    #                 basename = os.path.basename(file_path)
    #                 target_path = os.path.join(download_cfg.cmd.saveto, basename)
                    
    #                 if   tfx_ind == config.transfer_kind.upload:
    #                     cmdret = mysshlink.upload(file_path, target_path)
    #                 elif tfx_ind == config.transfer_kind.download:
    #                     cmdret = mysshlink.download(file_path, target_path)
    #                 else:
    #                     assert False, "wrong transfer kind !!!"
                            
    #                 final_cmdret.errcode = cmdret.errcode                    
    #                 final_cmdret.info_lines.append('--------------------------------------------------')
    #                 final_cmdret.info_lines.extend(cmdret.info_lines)                    
    #                 final_cmdret.error_lines.append('--------------------------------------------------')
    #                 final_cmdret.error_lines.extend(cmdret.error_lines)
                                        
    #                 if cmdret.errcode != 0:
    #                     break
            
    #         reply_data = {
    #             "taskid"  : download_cfg.cmd.taskid,
    #             "result"  : (0 == cmdret.errcode),
    #             "errcode" : final_cmdret.errcode,
    #             "stderr"  : final_cmdret.error_lines,
    #             "stdout"  : final_cmdret.info_lines,
    #         }

    #         dload_reply = config.download_reply(reply_data)
    #         dload_resp = config.download_response(dload_reply)
    #         dload_resp_text = dload_resp.toTEXT()
    #         logging.info("● file_resp_text={}".format(dload_resp_text))
    #         if is_json_report:
    #             print(json.dumps(json.loads(dload_resp_text), indent=2, sort_keys=True))
    #         else:
    #             print("[qemu-tasker] command result: {}".format(dload_resp_text.reply.result))

    #     except Exception as e:
    #         text = str(e)
    #         print(text)
    #         print("[qemu-tasker] {}".format(text))


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


    # def send_file_direct(self, file_cfg:config.file_config):
    #     file_from = file_cfg.cmd.pathfrom
    #     file_to   = file_cfg.cmd.pathto
        
    #     mode = LIBSSH2_SFTP_S_IRUSR | \
    #            LIBSSH2_SFTP_S_IWUSR | \
    #            LIBSSH2_SFTP_S_IRGRP | \
    #            LIBSSH2_SFTP_S_IROTH
        
    #     f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
        
    #     result = False
    #     errcode = -1
    #     stderr = ''
    #     stdout = ''
        
    #     rate = 0
    #     before = datetime.now()
        
    #     try:
    #         buf_size = 1024 * 1024 * 5
    #         file_stat = None
    #         realpath = ''
                        
    #         if file_cfg.cmd.sendfrom == config.target_kind.local:
    #             file_stat = os.stat(file_from)
    #             with open(file_from, 'rb', buf_size) as fh_src, \
    #                 self.conn_sftp.open(file_to, f_flags, mode) as fh_dst:
    #                 data = fh_src.read(buf_size)        
    #                 while data:
    #                     fh_dst.write(data)
    #                     data = fh_src.read(buf_size)

    #             diff = (datetime.now()-before)
    #             rate = (file_stat.st_size / 1024000.0) / diff.total_seconds()
                        
    #         elif file_cfg.cmd.sendfrom == config.target_kind.server:
    #             assert False , "Local <--> Server cannot NOT transfer directly"
    #             pass
                
    #         elif file_cfg.cmd.sendfrom == config.target_kind.guest:
    #             file_from = self.conn_sftp.realpath(file_from)
    #             if file_from.find(':') > 0 and file_from.startswith('/'):
    #                 file_from = file_from[1:].replace('/', '\\')
    #             file_stat = self.conn_sftp.stat(file_from)
    #             with self.conn_sftp.open(file_from, LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as fh_src, \
    #                 open(file_to, 'wb') as fh_dst:
    #                 for size, data in fh_src:
    #                     fh_dst.write(data)

    #             diff = (datetime.now()-before)                
    #             rate = (file_stat.filesize / 1024000.0) / diff.total_seconds()
                
    #         else:
    #             assert False , "switch-case missed, wrong path !!!"
    #             pass

    #         errcode = 0
    #         result = True
            
    #     except Exception as e:
    #         result = False
    #         stderr = "exception={0}".format(str(e))
    #         print(stderr)
    #         logging.info(stderr)

    #     finally:
    #         stdout = ("Finished writing remote file in {0}, transfer rate {1} MB/s".format(diff, rate))
    
    #         reply_data = {
    #             "taskid"  : file_cfg.cmd.taskid,
    #             "result"  : result,
    #             "errcode" : errcode,
    #             "stderr"  : [stderr],
    #             "stdout"  : [stdout],
    #         }
    #         return reply_data
