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
        self.breakup  = "breakup"

        # Control commands
        self.server   = "server"
        self.start    = "start"
        self.kill     = "kill"
        self.qmp      = "qmp"
        self.status   = "status"
        self.info     = "info"

        # Puppet commands
        self.puppet   = "puppet"
        self.execute  = "execute"
        self.upload   = "upload"
        self.list     = "list"
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


class connection_kind:
    def __init__(self):
        self.unknown      = "unknown"
        self.disabled     = "disabled"
        self.connecting   = "creating"
        self.connected    = "connected"
        self.disconnected = "disconnected"


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
    def __init__(self, qmp_port:int, ssh_port:int, puppet_port:int, ftp_port:int):
        self.qmp = qmp_port
        self.ssh = ssh_port
        self.pup = puppet_port
        self.ftp = ftp_port


class socket_address(config):
    def __init__(self, address:str, port:int):
        self.address:str = address
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


class connections_status:
    def __init__(self):
        self.QMP:connection_kind = connection_kind().unknown
        self.PUP:connection_kind = connection_kind().unknown
        self.FTP:connection_kind = connection_kind().unknown

class customized_return_command(command_return):
    def __init__(self, customized_error_message):
        self.error_lines = [customized_error_message]
        self.info_lines = []
        self.errcode = -99999
        self.data = None


return_command_unsupported  = customized_return_command('unsupported command')
return_command_unknown      = customized_return_command('unknown command')
return_command_wrong_taskid = customized_return_command('wrong taskid')
return_command_no_qemu_inst = customized_return_command('Failed to find the specific QEMU instance')
return_command_no_resp_data = customized_return_command('No response data')
return_command_socket_not_ready = customized_return_command('Socket is not ready')


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
    def __init__(self, os_kind:os_kind=os_kind().unknown,  homedir_path:str='', workdir_path:str='', workdir_name:str='', pushpool_name:str=''):
        self.os_kind = os_kind
        self.homedir_path = homedir_path
        self.workdir_path = workdir_path
        self.workdir_name = workdir_name
        self.pushpool_name = pushpool_name


class server_environment_information(config):
    def __init__(self, socket_addr:socket_address, workdir_path:str, pushpool_path:str):
        self.socket_addr = socket_addr
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
                 qcow2filename:str,
                 cmd_info:command_arguments):
        self.name = self.__class__.__name__

        self.longlife = longlife
        self.qcow2filename = qcow2filename
        self.cmd = cmd_info


class start_command_response_data(config):
    def __init__(self,
                 taskid:int,
                 pid:int,
                 port_fwd:forward_port,
                 server_info:server_environment_information,
                 guest_info:guest_environment_information,
                 conns_status:connections_status,
                 qemu_full_cmdargs:list,
                 status:task_status):
        self.name = self.__class__.__name__

        # Target
        self.taskid  = taskid
        self.pid     = pid
        self.status  = status

        # Resource
        self.forward     = port_fwd
        self.server_info = server_info
        self.guest_info  = guest_info
        self.qemu_full_cmdargs = qemu_full_cmdargs

        # Connections
        self.conns_status = conns_status
        self.is_connected_qmp = conns_status.QMP
        self.is_connected_pup = conns_status.PUP


# Kill command
kill_command_request_data  = generic_command_request_data
kill_command_response_data = generic_command_response_data


# Info command
class info_command_request_data(config):
    def __init__(self):
        self.name = self.__class__.__name__

class info_command_response_data(config):
    def __init__(self, variables:json, image_files:list):
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
                       workdir:str=None,
                       is_base64:bool=False):
        self.name = self.__class__.__name__

        self.taskid    = taskid
        self.program   = program
        self.argument  = argument
        self.workdir   = workdir
        self.is_base64 = is_base64

exec_command_response_data = generic_command_response_data


# =============================================================================
# File transfer commands
# =============================================================================
# Puppet command
class puppet_command_request_data(config):
    def __init__(self):
        self.name    = self.__class__.__name__


class puppet_command_response_data(config):
    def __init__(self):
        self.name    = self.__class__.__name__


# Execute command
execute_command_request_data  = exec_command_request_data
execute_command_response_data = exec_command_response_data


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
