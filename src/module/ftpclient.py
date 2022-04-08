# -*- coding: utf-8 -*-

import json
import os
import logging
from module import config
from ftplib import FTP

class ftpclient():


    def __init__(self, addr_info:config.socket_address, user_info:config.account_information=None):
        self.ftp = FTP()
        self.ftp.encoding = 'utf-8'
        self.ftp.connect(addr_info.address, addr_info.port)
        if user_info:
            self.ftp.login(user_info.username, user_info.password)
        else:
            self.ftp.login() # anonymous
        self.ftp.set_pasv(False);


    def __del__(self):
        self.close()


    def close(self):
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

    def try_mkdir(self, dir_path:str):
        cmdret = config.command_return ()

        try:
            full_pathname = self.ftp.mkd(dir_path)
            cmdret.info_lines.append("full_pathname={}".format(full_pathname))


        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("try_mkdir()"))
            cmdret.error_lines.append(str(e))
            cmdret.errcode = -1
            logging.info(cmdret.error_lines)

        finally:
            return cmdret


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


    def download(self, filepath_list:list, save_to_path:str):
        cmdret = config.command_return ()

        try:

            #
            # Check directory
            #
            if not os.path.exists(save_to_path):
                os.makedirs(save_to_path)

            if not os.path.exists(save_to_path):
                raise "Directory is not there !!! (save_to_path={})".format(save_to_path)

            #
            # Download files
            #
            for filepath in filepath_list:
                basename = os.path.basename(filepath)
                target_path = os.path.join(save_to_path, basename)
                resp = self.ftp.retrbinary("RETR " + filepath, open(target_path, 'wb').write)
                cmdret.info_lines.append(resp)

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
            # Try to create the directory then change directory
            #
            pwd = self.ftp.pwd()
            cmdret_mkdir = self.try_mkdir(dir_to_save)
            cmdret.info_lines.extend(cmdret_mkdir.info_lines)
            if cmdret_mkdir.errcode != 0:
                cmdret.error_lines.extend(cmdret_mkdir.error_lines)

            #
            # Upload files
            #
            for filepath in filepath_list:
                basename = os.path.basename(filepath)
                file = open(filepath,'rb')
                if file:
                    resp = self.ftp.storbinary('STOR ' + basename, file)
                    cmdret.info_lines.append(resp)
                    file.close()

            #
            # Change directory to the origin
            #
            resp = self.ftp.cwd(pwd)
            cmdret.info_lines.append(resp)

        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("upload()"))
            cmdret.error_lines.append(str(e))
            cmdret.errcode = -1
            logging.info(cmdret.error_lines)

        finally:
            return cmdret

