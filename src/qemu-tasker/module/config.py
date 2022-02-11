# -*- coding: utf-8 -*-
import json
import logging


class command_config:
    def __init__(self):
        self.taskid = -1

    def load_file(self, json_file_path):
        with open(json_file_path) as json_str:
            return json.load(json_str)

    def load_config_from_text(self, json_data_str):
        logging.info("config.py!config::load_config_str()")
        json_data = json.loads(json_data_str)
        self.load_config(json_data)

    def load_config_from_file(self, json_file_path):
        logging.info("config.py!config::load_config_file()")
        json_data = self.load_file(json_file_path)
        self.load_config(json_data)

class _qemu_config:
    def __init__(self): 
        self.prog = None
        self.args = []

class _ssh_config:
    def __init__(self): 
        self.username = None
        self.password = None

class task_command_config(command_config):
    def __init__(self):
        self.longlife = 0
        self.qemu = _qemu_config()
        self.ssh = _ssh_config()

    def load_config(self, json_data):
        self.longlife = json_data['longlife']
        self.qemu.prog = json_data['qemu']['prog']
        self.qemu.args = json_data['qemu']['args']
        self.ssh.username = json_data['ssh']['username']
        self.ssh.password = json_data['ssh']['password']


class kill_command_config(command_config):
    def __init__(self):
        self.taskid = -1

    def load_config(self, json_data):
        self.taskid = int(json_data['taskid'])

class exec_command_config(command_config):
    def __init__(self):
        self.taskid = -1
        self.program = ""
        self.arguments = []

    def load_config(self, json_data):
        self.taskid = int(json_data['taskid'])
        self.program = json_data['program']
        self.arguments = json_data['arguments']


