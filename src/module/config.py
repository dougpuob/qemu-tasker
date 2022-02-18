# -*- coding: utf-8 -*-
from array import array
from ctypes.wintypes import UINT
import json
import logging

import json
from os import kill

class config():
    def _try(self, o):
        try: 
            return o.__dict__
        except:
            return str(o).replace('\n', '')
    
    def toTEXT(self):
        #return json.dumps(self, default=lambda o: o.__dict__)
        return json.dumps(self, default=lambda o: self._try(o))

    def toJSON(self):
        return json.loads(self.toTEXT())
        
class socket_address(config):
    def __init__(self, addr:str, port:int):
        self.addr:str = addr
        self.port:int = port

class tcp_fwd_ports(config):
    def __init__(self, qmp:int, ssh:int):
        self.qmp = qmp
        self.ssh = ssh       

class qemu_longlife(config):
    def __init__(self, instance_maximum:int, longlife_minutes:int):
        self.instance_maximum = instance_maximum
        self.longlife_minutes = longlife_minutes

class ssh_login(config):
    def __init__(self, username:str, password:str): 
        self.username = username
        self.password = password


class server_config_default(config):
    def __init__(self):
        self.socket_address = socket_address("localhost", 12801)
        self.qemu_longlife = qemu_longlife(10, 10)
        self.ssh_login = ssh_login("dougpuob", "dougpuob")

class server_config(config):
    def __init__(self, json_data):
        """
        json_data = {
            "socket_address": {
                "addr": "localhost",
                "port": 12801
            },
            "qemu_longlife": {
                "instance_maximum": 10,
                "longlife_minutes": 10
            },
            "ssh_login": {
                "username": "dougpuob",
                "password": "dougpuob"
            }
        }
        """
        srv_cfg_def = server_config_default()
        
        if json_data.get('socket_address'):
            self.socket_address = json_data['socket_address']
        else:
            self.socket_address = srv_cfg_def.socket_address
            
        if json_data.get('qemu_longlife'):
            self.qemu_longlife = json_data['qemu_longlife']
        else:
            self.qemu_longlife = srv_cfg_def.qemu_longlife
            
        if json_data.get('ssh_login'):
            self.ssh_login = json_data['ssh_login']
        else:
            self.ssh_login = srv_cfg_def.ssh_login


class exec_arguments(config):
    def __init__(self, program:str, arguments:list): 
        self.program = program
        self.arguments = arguments

class qmp_arguments(config):
    def __init__(self, execute:str, arguments:json): 
        self.execute = execute
        self.arguments = arguments

class command_kind:
    def __init__(self):
        self.unknown = "unknown"        
        self.server  = "server"     
        self.start   = "start"     
        self.kill    = "kill"     
        self.exec    = "exec"     
        self.qmp     = "qmp" 
        self.info    = "info"  

class task_status:
    def __init__(self):
        self.unknown    = "unknown"
        self.creating   = "creating"
        self.connecting = "connecting"
        self.running    = "running"
        self.killing    = "killing"
        self.abandoned  = "abandoned"

class request(config):
    def __init__(self, command:str, data:json):
        print(data)
        self.command = command
        self.data = data

class response(config):
    def __init__(self, command:str, data:json):
        self.command = command
        self.data = data

#
# Default
# 
class default_reply(config):
    def __init__(self, data:json):        
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']
        
class default_response(config):
    def __init__(self, command:str, reply:default_reply):
        self.response = response(command, reply.toJSON())

        
#
# Bad
# 
class bad_reply(config):
    def __init__(self, data:json):        
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']
        
class bad_response(config):
    def __init__(self, reply:bad_reply):
        self.response = response(command_kind().unknown, reply.toJSON())

        


#
# Start
#
class start_command(config):
    def __init__(self, program:str, arguments:array, longlife:int, ssh_login:ssh_login):
        self.program = program
        self.arguments = arguments
        self.longlife = longlife
        self.ssh_login = ssh_login

class start_config(config):
    def __init__(self, data:json):
        self.cmd = start_command(data['program'],
                                 data['arguments'],
                                 data['longlife'],
                                 ssh_login(data['ssh_login']['username'], data['ssh_login']['password']))

class start_reply(config):
    def __init__(self, data:json):        
        self.taskid = data['taskid']
        self.fwd_ports = tcp_fwd_ports(data['fwd_ports']['qmp'], 
                                       data['fwd_ports']['ssh'])
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']


class  start_request(config):
    def __init__(self, command:start_command):
        self.request = request(command_kind().start, command.toJSON())

class digest_start_request(config):
    def __init__(self, req:json):
        assert (req['command'] == command_kind().start)
        self.request = request(command_kind().start, req['data'])

class start_response(config):
    def __init__(self, reply:start_reply):
        self.response = response(command_kind().start, reply.toJSON())


#
# Exec
#
class exec_command(config):
    def __init__(self, taskid:int, exec_args:exec_arguments):
        self.taskid = taskid
        self.exec_args = exec_args

class exec_config(config):
    def __init__(self, data:json):
        self.cmd  = exec_command(data['taskid'], 
                                 exec_arguments(data['exec_args']['program'], 
                                                data['exec_args']['arguments']))

class exec_reply(config):
    def __init__(self, data:json):
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

class exec_request(config):
    def __init__(self, command:exec_command):
        self.request = request(command_kind().exec, command.toJSON())

class digest_exec_request(config):
    def __init__(self, data:json):
        assert (data['command'] == command_kind().exec)
        self.request = request(data['command'], data['data'])

class exec_response(config):
    def __init__(self, reply:exec_reply):
        self.response = response(command_kind().exec, reply.toJSON())

class digest_exec_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = exec_reply(req['response']['data'])

#
# Kill
#
class kill_command(config):
    def __init__(self, taskid:int, killall:bool):
        self.taskid = taskid
        self.killall = killall

class kill_config(config):
    def __init__(self, data:json):
        self.cmd  = kill_command(data['taskid'], data['killall'])

class kill_reply(config):
    def __init__(self, data:json):        
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

class kill_request(config):
    def __init__(self, command:kill_command):
        self.request = request(command_kind().kill, command.toJSON())

class digest_kill_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = kill_reply(req['response']['data'])

class kill_response(config):
    def __init__(self, reply:kill_reply):
        self.response = response(command_kind().kill, reply.toJSON())


class digest_kill_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command'] 
        self.reply = kill_reply(req['response']['data'])


#
# QMP
#
class qmp_command(config):
    def __init__(self, taskid:int, execute:str, argsjson:json):
        self.taskid = taskid
        self.execute = execute
        self.argsjson = argsjson

class qmp_config(config):
    def __init__(self, data:json):
        self.cmd  = qmp_command(data['taskid'],
                                data['execute'],
                                data['argsjson'])

class qmp_reply(config):
    def __init__(self, data:json):
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

class qmp_request(config):
    def __init__(self, command:qmp_command):
        self.request = request(command_kind().qmp, command.toJSON())

class qmp_response(config):
    def __init__(self, reply:qmp_reply):
        self.response = response(command_kind().qmp, reply.toJSON())

class digest_qmp_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = qmp_reply(req['response']['data'])
