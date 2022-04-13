# -*- coding: utf-8 -*-

import json
import os
import logging
from module import config
from ftplib import FTP

class ftpclient():


    def __init__(self, socket_info:config.socket_address, user_info:config.account_information=None):
        self.ftp = FTP()
        self.ftp.encoding = 'utf-8'
        self.socket_info = socket_info
        self.user_info = user_info


    def __del__(self):
        self.close()


    def connect(self, passive_mode:bool=False):
        self.ftp.connect(self.socket_info.address, self.socket_info.port)
        self._is_connected = False

        if self.user_info:
            result = self.ftp.login(self.user_info.username, self.user_info.password)
        else:
            result = self.ftp.login() # anonymous

        logging.info("result={0}".format(result))
        if result == '230 Login successful.':
            self._is_connected = True

        if self._is_connected:
            if passive_mode:
                self.ftp.set_pasv(True);
            else:
                self.ftp.set_pasv(False);

        return self._is_connected


    def is_connected(self):
        return self._is_connected


    def close(self):
        if self.ftp:
            self.ftp.close()
            self.ftp = None


    def mkdir(self, dir_path:str):
        cmdret = config.command_return()

        try:
            full_pathname = self.ftp.mkd(dir_path)
            cmdret.info_lines.append("full_pathname={}".format(full_pathname))


        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("mkdir()"))
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

    def cd(self, dir_path:str):
        cmdret = config.command_return ()

        try:
            new_dir_path = self.ftp.cwd(dir_path)
            cmdret.data = new_dir_path

        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.cd("list()"))
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
                #cmdret.info_lines.append(resp)

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
                    cmdret.error_lines.append("File not found !!! (filepath={0})".format(filepath))

            if cmdret.errcode != 0:
                raise "File not found !!!"

            #
            # Change to target directory.
            #
            prev_dir = self.ftp.pwd()
            logging.info("prev_dir={0}".format(prev_dir))

            logging.info("dir_to_save={0}".format(dir_to_save))
            if dir_to_save:
                resp = self.ftp.cwd(dir_to_save)
                #cmdret.info_lines.append(resp)
                logging.info("resp={0}".format(resp))


            #
            # Upload files
            #
            for filepath in filepath_list:
                basename = os.path.basename(filepath)
                logging.info("filepath={0}".format(filepath))
                logging.info("basename={0}".format(basename))
                file = open(filepath,'rb')
                if file:
                    resp = self.ftp.storbinary('STOR ' + basename, file)
                    #cmdret.info_lines.append(resp)
                    file.close()

            #
            # Change directory to the origin
            #
            if dir_to_save:
                resp = self.ftp.cwd(prev_dir)
                logging.info("resp={0}".format(resp))
                #cmdret.info_lines.append(resp)

        except Exception as e:
            cmdret.error_lines.append('exception occured at {} function !!!'.format("upload()"))
            cmdret.error_lines.append(str(e))
            cmdret.errcode = -1
            logging.info(cmdret.error_lines)

        finally:
            return cmdret

