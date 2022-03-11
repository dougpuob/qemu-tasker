# -*- coding: utf-8 -*-
from array import array
from ctypes.wintypes import UINT
import json
import logging

import json
from os import kill

from enum import Enum


class cmd_return:
    def __init__(self):
        self.error_lines = []
        self.info_lines = []
        self.errcode = -9999
        self.data = None


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

class ssh_info(config):
    def __init__(self, targetaddr:str, targetport:int, username:str, password:str):
        self.targetaddr = targetaddr
        self.targetport = targetport
        self.username = username
        self.password = password

class ssh_login(config):
    def __init__(self, username:str, password:str):
        self.username = username
        self.password = password

class server_config_default(config):
    def __init__(self):
        self.socket_address = socket_address("localhost", 12801)
        self.qemu_longlife = qemu_longlife(10, 10)
        self.ssh_login = ssh_login("dougpuob", "dougpuob")

class ssh_conn_info(config):
    def __init__(self, host_addr, host_port, username, password):
        self.host = socket_address(host_addr, host_port)
        self.account = ssh_login(username, password)

class server_config(config):
    def __init__(self, json_data):
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

class exec_argument(config):
    def __init__(self, program:str, argument:str):
        self.program = program
        self.argument = argument

class qmp_arguments(config):
    def __init__(self, execute:str, arguments:json):
        self.execute = execute
        self.arguments = arguments

class os_kind:
    def __init__(self):
        self.unknown    = "unknown"
        self.windows    = "windows"
        self.linux      = "linux"
        self.macos      = "macos"

class command_kind:
    def __init__(self):
        self.unknown  = "unknown"
        self.server   = "server"
        self.start    = "start"
        self.kill     = "kill"
        self.exec     = "exec"
        self.qmp      = "qmp"
        self.file     = "file"
        self.list     = "list"
        self.download = "download"
        self.upload   = "upload"
        self.push     = "push"
        self.status   = "status"
        self.info     = "info"

class task_status:
    def __init__(self):
        self.unknown    = "unknown"
        self.waiting    = "waiting"
        self.creating   = "creating"
        self.connecting = "connecting"
        self.querying   = "querying"
        self.ready      = "ready"
        self.processing = "processing"
        self.killing    = "killing"

class request(config):
    def __init__(self, command:str, data:json):
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
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']
        self.cwd     = data['cwd']
        self.os      = data['os']
        self.fwd_ports = tcp_fwd_ports(data['fwd_ports']['qmp'],
                                       data['fwd_ports']['ssh'])

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
    def __init__(self, taskid:int, exec_arg:exec_argument, is_base64:bool):
        self.taskid = taskid
        self.exec_arg = exec_arg
        self.is_base64 = is_base64

class exec_config(config):
    def __init__(self, data:json):
        self.cmd  = exec_command(data['taskid'],
                                 exec_argument(data['exec_arg']['program'],
                                                data['exec_arg']['argument']),
                                 data['is_base64'])

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
    def __init__(self, taskid:int, execute:str, argsjson:json, is_base64:bool):
        self.taskid = taskid
        self.execute = execute
        self.argsjson = argsjson
        self.is_base64 = is_base64

class qmp_config(config):
    def __init__(self, data:json):
        self.cmd  = qmp_command(data['taskid'],
                                data['execute'],
                                data['argsjson'],
                                data['is_base64'])

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

#
# List
#
class list_command(config):
    def __init__(self, taskid:int, dirpath:str):
        self.taskid = taskid
        self.dirpath = dirpath

class list_config(config):
    def __init__(self, data:json):
        self.cmd  = list_command(data['taskid'], data['dirpath'])

class list_reply(config):
    def __init__(self, data:json):
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

        # extra data
        self.readdir = data['readdir']

class list_request(config):
    def __init__(self, command:list_command):
        self.request = request(command_kind().list, command.toJSON())

class digest_list_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = list_reply(req['response']['data'])

class list_response(config):
    def __init__(self, reply:list_reply):
        self.response = response(command_kind().list, reply.toJSON())

class digest_list_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = list_reply(req['response']['data'])


#
# Download
#
class download_command(config):
    def __init__(self, taskid:int, files:list, dirpath:str):
        self.taskid = taskid

        self.files = files
        self.dirpath = dirpath

class download_config(config):
    def __init__(self, data:json):
        self.cmd  = download_command(data['taskid'], data['files'], data['dirpath'])

class download_reply(config):
    def __init__(self, data:json):
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

class download_request(config):
    def __init__(self, command:download_command):
        self.request = request(command_kind().download, command.toJSON())

class digest_download_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = download_reply(req['response']['data'])

class download_response(config):
    def __init__(self, reply:download_reply):
        self.response = response(command_kind().download, reply.toJSON())

class digest_download_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = download_reply(req['response']['data'])


#
# Upload
#
class upload_command(config):
    def __init__(self, taskid:int, files:list, dirpath:str):
        self.taskid   = taskid

        self.files = files
        self.dirpath = dirpath

class upload_config(config):
    def __init__(self, data:json):
        self.cmd  = upload_command(data['taskid'], data['files'], data['dirpath'])

class upload_reply(config):
    def __init__(self, data:json):
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

class upload_request(config):
    def __init__(self, command:upload_command):
        self.request = request(command_kind().upload, command.toJSON())

class digest_upload_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = upload_reply(req['response']['data'])

class upload_response(config):
    def __init__(self, reply:upload_reply):
        self.response = response(command_kind().upload, reply.toJSON())

class digest_upload_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = upload_reply(req['response']['data'])


#
# Push
#
class push_command(config):
    def __init__(self, taskid:int):
        self.taskid   = taskid

class push_config(config):
    def __init__(self, data:json):
        self.cmd  = push_command(data['taskid'])

class push_reply(config):
    def __init__(self, data:json):
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

class push_request(config):
    def __init__(self, command:push_command):
        self.request = request(command_kind().push, command.toJSON())

class digest_push_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = push_reply(req['response']['data'])

class push_response(config):
    def __init__(self, reply:push_reply):
        self.response = response(command_kind().push, reply.toJSON())

class digest_push_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = push_reply(req['response']['data'])

#
# Status
#
class status_command(config):
    def __init__(self, taskid:int):
        self.taskid = taskid

class status_config(config):
    def __init__(self, data:json):
        self.cmd  = status_command(data['taskid'])

class status_reply(config):
    def __init__(self, data:json):
        # base
        self.taskid  = data['taskid']
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

        # extra
        self.pid = data['pid']
        self.status = data['status'] # status:task_status
        self.fwd_ports = tcp_fwd_ports(data['fwd_ports']['qmp'],
                                       data['fwd_ports']['ssh'])
        self.ssh_info = ssh_info(data['ssh_info']['targetaddr'],
                                 data['ssh_info']['targetport'],
                                 data['ssh_info']['username'],
                                 data['ssh_info']['password'])
        self.host_pushpool = data['host_pushpool']
        self.guest_pushpool = data['guest_pushpool']
        self.guest_work_dir = data['guest_work_dir']        
        self.guest_os_kind = data['guest_os_kind']        
        self.is_connected_qmp = data['is_connected_qmp']
        self.is_connected_ssh = data['is_connected_ssh']

class status_request(config):
    def __init__(self, command:status_command):
        self.request = request(command_kind().status, command.toJSON())

class digest_status_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = status_reply(req['response']['data'])

class status_response(config):
    def __init__(self, reply:status_reply):
        self.response = response(command_kind().status, reply.toJSON())

class digest_status_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = status_reply(req['response']['data'])


#
# Info
#
class info_command(config):
    def __init__(self):
        pass

class info_config(config):
    def __init__(self):
        self.cmd  = info_command()

class info_reply(config):
    def __init__(self, data:json):
        # base
        self.result  = data['result']
        self.errcode = data['errcode']
        self.stderr  = data['stderr']
        self.stdout  = data['stdout']

        # extra
        self.variables = data['variables']
        self.instances = data['instances']
        self.images = data['images']
        

class info_request(config):
    def __init__(self, command:info_command):
        self.request = request(command_kind().info, command.toJSON())

class digest_info_request(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = info_reply(req['response']['data'])

class info_response(config):
    def __init__(self, reply:info_reply):
        self.response = response(command_kind().info, reply.toJSON())

class digest_info_response(config):
    def __init__(self, req:json):
        self.command = req['response']['command']
        self.reply = info_reply(req['response']['data'])

