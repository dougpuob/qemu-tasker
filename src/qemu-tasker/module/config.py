# -*- coding: utf-8 -*-
import json
import logging


class config:
    def load_file(self, file_path):
        with open(file_path) as json_str:
            return json.load(json_str)

class _qemu_config:
    def __init__(self): 
        self.prog = None
        self.args = []

class _ssh_config:
    def __init__(self): 
        self.username = None
        self.password = None

class task_config(config):
    def __init__(self):         
        logging.info("config.py!task_config::__init__()")
        self.longlife = 0
        self.qemu = _qemu_config()
        self.ssh = _ssh_config()

    def load_config(self, json_data):
        logging.info("config.py!task_config::load_config()")
        assert json_data['longlife']        , "json_data['longlife']"
        assert json_data['qemu']['prog']    , "json_data['qemu']['prog']"
        assert json_data['qemu']['args']    , "json_data['qemu']['args']"
        assert json_data['ssh']['username'] , "json_data['ssh']['username']"
        assert json_data['ssh']['password'] , "json_data['ssh']['password']"

        self.longlife = json_data['longlife']
        self.qemu.prog = json_data['qemu']['prog']
        self.qemu.args = json_data['qemu']['args']
        self.ssh.username = json_data['ssh']['username']
        self.ssh.password = json_data['ssh']['password']

    def load_config_str(self, json_str):
        logging.info("config.py!task_config::load_config_str()")
        json_data = json.loads(json_str)
        self.load_config(json_data)

    def load_config_file(self, file_path):
        logging.info("config.py!task_config::load_config_file()")
        json_data = self.load_file(file_path)
        self.load_config(json_data)

            