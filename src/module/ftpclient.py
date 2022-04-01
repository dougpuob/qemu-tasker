# -*- coding: utf-8 -*-

import json
import os
import logging
from module import config
from ftplib import FTP

class ftpclient():


    def __init__(self, addr_info:config.socket_address, user_info:config.account_information):
        self.ftp = FTP()
        self.ftp.encoding = 'utf-8'
        self.ftp.connect(addr_info.address, addr_info.port)
        self.ftp.login(user_info.username, user_info.password)


    def __del__(self):
        if self.ftp:
            self.ftp.close()
            self.ftp = None


    # def cd(self, path:str):
    #     cmdret = config.command_return ()

    #     try:
    #         self.ftp.cwd(path)

    #     except Exception as e:
    #         cmdret.error_lines.append('exception occured at {} function !!!'.format("list()"))
    #         cmdret.error_lines.append(str(e))
    #         cmdret.errcode = -1
    #         logging.info(cmdret.error_lines)

    #     finally:
    #         return cmdret

    def list(self, dir_path:str):
        cmdret = config.command_return ()

        try:
            dir_list = self.ftp.nlst(dir_path)
            cmdret.data = dir_list

        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("list()"))
            cmdret.error_lines.append(str(e))
            cmdret.errcode = -1
            logging.info(cmdret.error_lines)

        finally:
            return cmdret


    def download(self, file_path:str, save_to_path:str):
        cmdret = config.command_return ()

        try:
            pwd = self.ftp.pwd()
            dirname = os.path.dirname(file_path)

            dir_changed = False
            if pwd != dirname:
                dir_changed = True
                self.ftp.cwd(dirname)

            basename = os.path.basename(file_path)
            self.ftp.retrbinary("RETR " + basename ,open(save_to_path, 'wb').write)

            if dir_changed:
                self.ftp.cwd(pwd)

        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("download()"))
            cmdret.error_lines.append(str(e))
            cmdret.errcode = -1
            logging.info(cmdret.error_lines)

        finally:
            return cmdret


    def upload(self, filepath_list:list, dir_to_save:str):
        cmdret = config.command_return ()

        try:
            #
            # Check files
            #
            for filepath in filepath_list:
                if not os.path.exists(filepath):
                    cmdret.errcode = -1
                    cmdret.error_lines.append("File not found !!! (filepath={})".format(filepath))

            if cmdret.errcode != 0:
                raise "File not found !!!"

            #
            # Change directory then upload files
            #
            pwd = self.ftp.pwd()
            self.ftp.cwd(dir_to_save)

            for filepath in filepath_list:
                basename = os.path.basename(filepath)
                file = open(filepath,'rb')
                if file:
                    resp = self.ftp.storbinary('STOR ' + basename, file)
                    cmdret.info_lines.append(resp)
                    file.close()

            self.ftp.cwd(pwd)

        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("upload()"))
            cmdret.error_lines.append(str(e))
            cmdret.errcode = -1
            logging.info(cmdret.error_lines)

        finally:
            return cmdret

