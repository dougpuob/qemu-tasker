# -*- coding: utf-8 -*-
import os
import platform
import logging

from module import config
from module.path import OsdpPath
from module.pyrc.rc import rcserver

class puppet_server():

    def __init__(self, setting):
        self.setting = setting
        self.osdppath = OsdpPath()

        # Resource
        if platform.system() == 'Linux':
            self.oskind = config.os_kind().linux
        elif platform.system() == 'Darwin':
            self.oskind = config.os_kind().macos
        elif platform.system() == 'Windows':
            self.oskind = config.os_kind().windows
        else:
            self.oskind = config.os_kind().unknown

        self.WORK_DIR = os.path.join(os.path.expanduser('~'), 'qemu-tasker')
        self.WORK_DIR = self.osdppath.normpath(self.WORK_DIR, self.oskind)
        if not os.path.exists(self.WORK_DIR):
            os.mkdir(self.WORK_DIR)
        os.chdir(self.WORK_DIR)

        self.pyrc_server = rcserver(self.setting.Puppet.Address, self.setting.Puppet.Port.Cmd)


    def __del__(self):
        if self.pyrc_server:
            self.pyrc_server.stop()


    def start(self):
        logging.info('Server socket addr_info={}'.format(self.pyrc_server.get_addr_info()))
        self.pyrc_server.start()

