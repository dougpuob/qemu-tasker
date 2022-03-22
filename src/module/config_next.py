# -*- coding: utf-8 -*-

import json
from pickle import NONE
from types import SimpleNamespace


# =============================================================================
# Enumerations
# =============================================================================
class action_kind:
    def __init__(self):
        self.unknown  = "unknown"
        self.request  = "request"
        self.response = "response"


class command_kind:
    def __init__(self):
        self.unknown  = "unknown"

        # Control commands
        self.server   = "server"
        self.start    = "start"
        self.kill     = "kill"
        self.exec     = "exec"
        self.qmp      = "qmp"
        self.status   = "status"
        self.info     = "info"

        # File transfer commands
        self.list     = "list"
        self.upload   = "upload"
        self.download = "download"

        # Synchronization command
        self.push     = "push"
        self.signal   = "signal"


class os_kind:
    def __init__(self):
        self.unknown    = "unknown"
        self.windows    = "windows"
        self.linux      = "linux"
        self.macos      = "macos"


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


# =============================================================================
# Basic data structures
# =============================================================================

class config():
    def _try(self, o):
        try:
            return o.__dict__
        except:
            return str(o).replace('\n', '')

    def toTEXT(self):
        return json.dumps(self, default=lambda o: self._try(o))

    def toJSON(self):
        return json.loads(self.toTEXT())

    def toCLASS(self, text=None):
        if text == None:
            text = self.toTEXT()
        return json.loads(text, object_hook=lambda d: SimpleNamespace(**d))


class server_name(config):
    def __init__(self, name:str, port:int):
        self.name  = name
        self.port  = port


class forward_port(config):
    def __init__(self, qmp_port:int, ssh_port:int):
        self.qmp = qmp_port
        self.ssh = ssh_port


class socket_address(config):
    def __init__(self, addr:str, port:int):
        self.addr:str = addr
        self.port:int = port


class account_information(config):
    def __init__(self, username:str, password:str):
        self.username = username
        self.password = password


class ssh_information(config):
    def __init__(self, addr_info:socket_address, account_info:account_information):
        self.target  = addr_info
        self.account = account_info


class command_argument(config):
    def __init__(self, program:str, argument:str):
        self.program = program
        self.argument = argument


class command_arguments(config):
    def __init__(self, program:str, arguments:list):
        self.program = program
        self.arguments = arguments


class command_return:
    def __init__(self):
        self.error_lines = []
        self.info_lines = []
        self.errcode = 0
        self.data = None


    def clear(self):
        self.errcode = 0
        self.error_lines.clear()
        self.info_lines.clear()


class transaction_capsule(config):
    def __init__(self, act_kind:action_kind,
                       cmd_kind:command_kind,
                       result:command_return=None,
                       data=None):

        self.act_kind = act_kind
        self.cmd_kind = cmd_kind

        if result:
            self.result = result
        else:
            self.result = ''

        if data:
            self.data = data
        else:
            self.data = ''


class guest_environment_information(config):
    def __init__(self, os_kind:os_kind=os_kind().unknown,  homedir_path:str='', workdir_name:str='', pushpool_name:str=''):
        self.os_kind = os_kind
        self.homedir_path = homedir_path
        self.workdir_name = workdir_name
        self.pushpool_name = pushpool_name


class server_environment_information(config):
    def __init__(self, workdir_path:str, pushpool_path:str):
        self.workdir_path = workdir_path
        self.pushpool_path = pushpool_path


class generic_command_request_data(config):
    def __init__(self, taskid):
        self.name = self.__class__.__name__
        self.taskid = taskid


class generic_command_response_data(config):
    def __init__(self, taskid):
        self.name = self.__class__.__name__
        self.taskid = taskid


# =============================================================================
# Control command
# =============================================================================

# Start command
class start_command_request_data(config):
    def __init__(self,
                 longlife:int,
                 ssh_info:ssh_information,
                 cmd_info:command_arguments):
        self.name = self.__class__.__name__

        self.longlife = longlife
        self.cmd = cmd_info
        self.ssh_info = ssh_info


class start_command_response_data(config):
    def __init__(self,
                 taskid:int,
                 pid:int,
                 port_fwd:forward_port,
                 ssh_conn_info:ssh_information,
                 server_info:server_environment_information,
                 guest_info:guest_environment_information,
                 is_connected_qmp:bool,
                 is_connected_ssh:bool):
        self.name = self.__class__.__name__

        # Target
        self.taskid    = taskid
        self.pid       = pid

        # Resource
        self.forward     = port_fwd
        self.ssh         = ssh_conn_info
        self.server_info = server_info
        self.guest_info  = guest_info

        # Connections
        self.is_connected_qmp = is_connected_qmp
        self.is_connected_ssh = is_connected_ssh


# Kill command
kill_command_request_data  = generic_command_request_data
kill_command_response_data = generic_command_response_data


# Info command
class info_command_request_data(config):
    def __init__(self):
        self.name = self.__class__.__name__

class info_command_response_data(config):
    def __init__(self, variables:map, image_files:list):
        self.name = self.__class__.__name__

        self.variables = variables
        self.image_files = image_files


# Status command
status_command_request_data  = generic_command_request_data
status_command_response_data = start_command_response_data


# QMP command
class qmp_command_request_data(config):
    def __init__(self, taskid:int,
                       execute:str,
                       argsjson:json,
                       is_base64:bool=False):
        self.name = self.__class__.__name__

        self.taskid    = taskid
        self.execute   = execute
        self.argsjson  = argsjson
        self.is_base64 = is_base64

qmp_command_response_data = generic_command_response_data


# Exec command
class exec_command_request_data(config):
    def __init__(self, taskid:int,
                       program:str,
                       argument:str,
                       is_base64:bool=False):
        self.name = self.__class__.__name__

        self.taskid    = taskid
        self.program   = program
        self.argument  = argument
        self.is_base64 = is_base64

exec_command_response_data = generic_command_response_data


# =============================================================================
# File transfer commands
# =============================================================================

# List command
class list_command_request_data(config):
    def __init__(self, taskid:int,
                       dstdir:str):
        self.name    = self.__class__.__name__
        self.taskid  = taskid
        self.dstdir = dstdir

class list_command_response_data(config):
    def __init__(self, taskid:int,
                       readdir:list):
        self.name    = self.__class__.__name__
        self.readdir = readdir


# Download command
class download_command_request_data(config):
    def __init__(self, taskid:int,
                       files:list,
                       dstdir:str):
        self.name    = self.__class__.__name__
        self.taskid  = taskid
        self.files   = files
        self.dstdir = dstdir

download_command_response_data = generic_command_response_data


# Upload command
class upload_command_request_data(config):
    def __init__(self, taskid:int,
                       files:list,
                       dstdir:str):
        self.name    = self.__class__.__name__
        self.taskid  = taskid
        self.files   = files
        self.dstdir = dstdir

upload_command_response_data = generic_command_response_data


# =============================================================================
# Synchronization commands
# =============================================================================

# Push command
push_command_request_data  = generic_command_request_data
push_command_response_data = generic_command_response_data


# Signal command
signal_command_request_data  = None
signal_command_response_data = None