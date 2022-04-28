import os
import sys
import time
import json
import socket
import base64
import struct
import logging
import platform
import subprocess
import threading

from enum import Enum
from types import SimpleNamespace

#
# definition of unit
#
_1KB_ = 1024
_1MB_ = _1KB_*1024


#
# definition for pyrc
#
_WAIT_TIMEOUT_ = 30
_HEADER_SIZE_ = 16
_CHUNK_SIZE_ = _1KB_*512
_BUFFER_SIZE_ = _1MB_*2


#
# Signature of headers
#
_SIGNATURE_ECHO___ = b'$SiGEcH$'
_SIGNATURE_UPLOAD_ = b'$SiGUpL$'
_SIGNATURE_DOWNLO_ = b'$SiGDoW$'
_SIGNATURE_EXECUT_ = b'$SiGExE$'
_SIGNATURE_LIST___ = b'$SiGLiS$'
_SIGNATURE_TEXT___ = b'$SiGTex$'


class config():
    def _try(self, o):
        try:
            return o.__dict__
        except Exception:
            return str(o).replace('\n', '')

    def toTEXT(self):
        return json.dumps(self, default=lambda o: self._try(o)).strip()

    def toJSON(self):
        return json.loads(self.toTEXT())

    def toCLASS(self, text=None):
        if not text:
            text = self.toTEXT()
        return json.loads(text, object_hook=lambda d: SimpleNamespace(**d))


#
# Exception definitions
#
class rcresult(config):
    def __init__(self, errcode: int = 0, errmsg: str = ''):
        self.errcode = errcode
        self.text = errmsg
        self.data = None


# General error
error_unknown = rcresult(1, 'Unknown error')
error_file_already_exist = rcresult(2, 'File already exist')
error_file_not_found = rcresult(3, 'File not found')
error_path_not_exist = rcresult(4, 'Path is not exist')
error_not_a_file = rcresult(5, 'The specific path is not a file')
error_not_a_folder = rcresult(6, 'The specific path is not a folder')
error_file_not_identical = rcresult(7, 'File length is not identical')
error_exception = rcresult(9, 'An exception rised')

# Streaming
error_wait_timeout_streaming = rcresult(50, 'Wait streaming timeout')
error_wait_timeout_done = rcresult(51, 'Wait done timeout')

# Process
error_exception_proc_wait_timeout = rcresult(60, 'Wait timeout a process')


#
# Enumeration definitions
#
class action_name(Enum):
    unknown = 0
    upload = 1
    download = 2
    list = 3
    execute = 4
    text = 5
    echo = 99


class action_kind(Enum):
    unknown = 0
    ask = 1
    data = 2
    done = 3


class execute_subcmd(Enum):
    unknown = 0
    start = 1
    query = 2
    kill = 3


class proc_status(Enum):
    unknown = 0
    unstart = 1
    running = 2
    killing = 3
    killed = 4
    terminated = 5
    exception = 6


#
# Class definitions
#
class computer_info(config):
    def __init__(self, osname: str = 'unknown', homedir: str = ''):
        self.osname = osname
        self.homedir = homedir


class inncmd_mkdir(config):
    def __init__(self, path: str, result: bool = False):
        self.path = path
        self.result = result


class execmdarg(config):
    def __init__(self,
                 program: bytes,
                 argument: bytes = '',
                 workdir: bytes = '.',
                 isbase64: bool = False):
        self.program = program
        self.argument = argument
        self.workdir = workdir
        self.isbase64 = isbase64


class execresult(config):
    def __init__(self):
        self.errcode = 0
        self.stdout = []
        self.stderr = []
        self.data = None


class async_process():

    def __init__(self, tag):
        self.program = ''
        self.argument = ''
        self.workdir = '.'
        self.status = proc_status.unknown
        self.execrs = execresult()
        self.tag: int = tag

        self.thread = threading.Thread(target=self._thread_start)
        self.thread.daemon = True

    def _thread_start(self):
        self.status = proc_status.running

        try:
            fullcmd = self.program
            if '' != self.argument:
                fullcmd += ' ' + self.argument
            self.proc = subprocess.Popen(fullcmd,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         shell=True,
                                         cwd=self.workdir)
            try:
                self.execrs.errcode = self.proc.wait(_WAIT_TIMEOUT_)
                logging.error('fullcmd={} errcode={}'.format(fullcmd, self.execrs.errcode))

                stdout_lines = [line.decode('utf-8', errors="ignore").rstrip() for line in self.proc.stdout.readlines()]
                self.execrs.stdout.extend(stdout_lines)

                stderr_lines = [line.decode('utf-8', errors="ignore").rstrip() for line in self.proc.stderr.readlines()]
                self.execrs.stderr.extend(stderr_lines)

                self.status = proc_status.terminated

            except Exception as Err:
                self.execrs.errcode = 100000
                self.status = proc_status.exception
                self.execrs.stderr.append(Err)

        except subprocess.TimeoutExpired as Err:
            logging.exception(Err)
            self.status = proc_status.exception
            self.execrs.errcode = error_exception_proc_wait_timeout.errcode
            self.execrs.stderr.append(error_exception_proc_wait_timeout.text)
            self.execrs.stderr.append(str(Err))

        except Exception as Err:
            logging.exception(Err)
            self.status = proc_status.exception
            self.execrs.errcode = error_exception.errcode
            self.execrs.stderr.append(error_exception.text)
            self.execrs.stderr.append(str(Err))

        finally:
            pass

    def run(self, program: str,
            argument: str = '',
            workdir: str = '.'):
        self.program = program
        self.argument = argument
        self.workdir = workdir

        if self.status != proc_status.unknown:
            return

        if self.thread:
            self.thread.start()
            self.status = proc_status.running

    def kill(self):
        if self.proc:
            self.proc.terminate()
            self.status = proc_status.killed

        self.thread = None

    def get_status(self):
        return self.status

    def get_tag(self):
        return self.tag


class header_echo():
    def __init__(self, kind: action_kind = action_kind.unknown, data: bytes = b''):

        self.data = b''

        self._STRUCT_FORMAT_ = '8s' + 'iiiii' + 'iii' + 'p'

        self.signature: bytes = _SIGNATURE_ECHO___

        self.header_size: int = 0
        self.total_size: int = 0
        self.payload_size: int = 0
        self.action_name: int = action_name.echo.value
        self.action_kind: int = kind.value

        self.chunk_size: int = len(data)
        self.chunk_count: int = 0
        self.chunk_index: int = 0

        self.payload: bytes = data

    def pack(self):
        self.header_size = struct.calcsize(self._STRUCT_FORMAT_)
        self.payload_size = self.chunk_size
        self.total_size = self.header_size + self.payload_size

        rawdata = struct.pack(self._STRUCT_FORMAT_,
                              self.signature,

                              self.header_size,
                              self.total_size,
                              self.payload_size,
                              self.action_name,
                              self.action_kind,

                              self.chunk_size,
                              self.chunk_count,
                              self.chunk_index,

                              self.payload)

        rawdata += self.payload
        return rawdata

    def unpack(self, data: bytes):
        if len(data) <= _HEADER_SIZE_:
            return None

        hdr_size: int = int.from_bytes(data[8:11], 'little')
        hdr_only: bytes = data[:hdr_size]

        hdr = header_echo()

        # Header files
        unpack = struct.unpack(self._STRUCT_FORMAT_, hdr_only)
        hdr.signature = unpack[0]
        hdr.header_size = unpack[1]
        hdr.total_size = unpack[2]
        hdr.payload_size = unpack[3]
        hdr.action_name = unpack[4]
        hdr.action_kind = unpack[5]
        hdr.chunk_size = unpack[6]
        hdr.chunk_count = unpack[7]
        hdr.chunk_index = unpack[8]

        # Payload
        hdr.payload = data[hdr_size:]

        # Unpack data from payload
        hdr.data = hdr.payload

        return hdr


class header_upload():
    def __init__(self, kind: action_kind = action_kind.unknown,
                 filename: str = '',
                 filesize: int = 0,
                 dstdirpath: str = '.',
                 data: bytes = b''):

        if filename is None:
            filename = ''

        if dstdirpath is None:
            dstdirpath = '.'

        self._STRUCT_FORMAT_ = '8s' + 'iiiiii' + 'iii' + 'ii' + 'p'

        # Unpack payload fields
        self.filename = b''
        self.dstdirpath = b''
        self.data = b''

        self.signature: bytes = _SIGNATURE_UPLOAD_

        self.header_size: int = 0
        self.total_size: int = 0
        self.payload_size: int = 0
        self.file_size: int = filesize
        self.action_name: int = action_name.upload.value
        self.action_kind: int = kind.value

        self.chunk_size: int = len(data)
        self.chunk_count: int = 0
        self.chunk_index: int = 0

        self.length_filename: int = len(filename)
        self.length_dirpath: int = len(dstdirpath)

        self.payload: bytes = (filename.encode('utf-8') +
                               dstdirpath.encode('utf-8') +
                               data)

    def pack(self):
        self.header_size = struct.calcsize(self._STRUCT_FORMAT_)
        self.payload_size = (self.length_filename +
                             self.length_dirpath +
                             self.chunk_size)
        self.total_size = self.header_size + self.payload_size

        rawdata = struct.pack(self._STRUCT_FORMAT_,
                              self.signature,

                              self.header_size,
                              self.total_size,
                              self.payload_size,
                              self.file_size,
                              self.action_name,
                              self.action_kind,

                              self.chunk_size,
                              self.chunk_count,
                              self.chunk_index,

                              self.length_filename,
                              self.length_dirpath,

                              self.payload)

        rawdata += self.payload
        return rawdata

    def unpack(self, data: bytes):
        if len(data) <= _HEADER_SIZE_:
            return None

        hdr_size: int = int.from_bytes(data[8:11], 'little')
        hdr_only: bytes = data[:hdr_size]

        hdr = header_upload()

        # Header files
        unpack = struct.unpack(self._STRUCT_FORMAT_, hdr_only)
        hdr.signature = unpack[0]
        hdr.header_size = unpack[1]
        hdr.total_size = unpack[2]
        hdr.payload_size = unpack[3]
        hdr.file_size = unpack[4]
        hdr.action_name = unpack[5]
        hdr.action_kind = unpack[6]
        hdr.chunk_size = unpack[7]
        hdr.chunk_count = unpack[8]
        hdr.chunk_index = unpack[9]
        hdr.length_filename = unpack[10]
        hdr.length_dirpath = unpack[11]

        # Payload
        hdr.payload = data[hdr_size:]

        # Unpack data from payload
        pos1 = 0
        pos2 = hdr.length_filename
        if pos2 - pos1 > 0:
            hdr.filename = str(hdr.payload[:pos2], 'utf-8')

        pos1 = hdr.length_filename
        pos2 = hdr.length_filename + hdr.length_dirpath
        if pos2 - pos1 > 0:
            hdr.dstdirpath = str(hdr.payload[pos1:pos2], 'utf-8')

        pos1 = hdr.length_filename + hdr.length_dirpath
        hdr.data = hdr.payload[pos1:]

        return hdr


class header_download():
    def __init__(self, kind: action_kind = action_kind.unknown,
                 filepath: str = '',
                 filesize: int = 0,
                 data: bytes = b''):

        self._STRUCT_FORMAT_ = '8s' + 'iiiiii' + 'iii' + 'i' + 'p'

        # Unpack payload fields
        self.filepath = b''
        self.data = b''

        self.signature: bytes = _SIGNATURE_DOWNLO_

        self.header_size: int = 0
        self.total_size: int = 0
        self.payload_size: int = 0
        self.file_size: int = filesize
        self.action_name: int = action_name.download.value
        self.action_kind: int = kind.value

        self.chunk_size: int = len(data)
        self.chunk_count: int = 0
        self.chunk_index: int = 0

        self.length_filepath: int = len(filepath)

        self.payload: bytes = b''
        if filepath:
            self.payload += filepath.encode('utf-8')
        if data:
            self.payload += data

    def pack(self):
        self.header_size = struct.calcsize(self._STRUCT_FORMAT_)
        self.payload_size = (self.length_filepath +
                             self.chunk_size)
        self.total_size = self.header_size + self.payload_size

        rawdata = struct.pack(self._STRUCT_FORMAT_,
                              self.signature,

                              self.header_size,
                              self.total_size,
                              self.payload_size,
                              self.file_size,
                              self.action_name,
                              self.action_kind,

                              self.chunk_size,
                              self.chunk_count,
                              self.chunk_index,

                              self.length_filepath,

                              self.payload)

        rawdata += self.payload
        return rawdata

    def unpack(self, data: bytes):
        if len(data) <= _HEADER_SIZE_:
            return None

        hdr_size: int = int.from_bytes(data[8:11], 'little')
        hdr_only: bytes = data[:hdr_size]

        hdr = header_download()

        # Header files
        unpack = struct.unpack(self._STRUCT_FORMAT_, hdr_only)
        hdr.signature = unpack[0]
        hdr.header_size = unpack[1]
        hdr.total_size = unpack[2]
        hdr.payload_size = unpack[3]
        hdr.file_size = unpack[4]
        hdr.action_name = unpack[5]
        hdr.action_kind = unpack[6]
        hdr.chunk_size = unpack[7]
        hdr.chunk_count = unpack[8]
        hdr.chunk_index = unpack[9]
        hdr.length_filepath = unpack[10]

        # Payload
        hdr.payload = data[hdr_size:]

        # Unpack data from payload
        pos1 = 0
        pos2 = hdr.length_filepath
        if pos2 - pos1 > 0:
            hdr.filepath = str(hdr.payload[:pos2], 'utf-8')

        pos1 = hdr.length_filepath
        hdr.data = hdr.payload[pos1:]

        return hdr


class header_list():
    def __init__(self,
                 kind: action_kind = action_kind.unknown,
                 dstdirpath: str = '',
                 data: bytes = b''):

        self._STRUCT_FORMAT_ = '8s' + 'iiiii' + 'iii' + 'i' + 'p'

        # Unpack payload fields
        self.dstdirpath = b''
        self.data = b''

        self.signature: bytes = _SIGNATURE_LIST___

        self.header_size: int = 0
        self.total_size: int = 0
        self.payload_size: int = 0
        self.action_name: int = action_name.list.value
        self.action_kind: int = kind.value

        self.chunk_size: int = len(data)
        self.chunk_count: int = 0
        self.chunk_index: int = 0

        self.length_dirpath: int = len(dstdirpath)

        self.payload: bytes = (dstdirpath.encode('utf-8') +
                               data)

    def pack(self):
        self.header_size = struct.calcsize(self._STRUCT_FORMAT_)
        self.payload_size = (self.length_dirpath +
                             self.chunk_size)
        self.total_size = self.header_size + self.payload_size

        rawdata = struct.pack(self._STRUCT_FORMAT_,
                              self.signature,

                              self.header_size,
                              self.total_size,
                              self.payload_size,
                              self.action_name,
                              self.action_kind,

                              self.chunk_size,
                              self.chunk_count,
                              self.chunk_index,

                              self.length_dirpath,

                              self.payload)

        rawdata += self.payload
        return rawdata

    def unpack(self, data: bytes):
        if len(data) <= _HEADER_SIZE_:
            return None

        hdr_size: int = int.from_bytes(data[8:11], 'little')
        hdr_only: bytes = data[:hdr_size]

        hdr = header_list()

        # Header files
        unpack = struct.unpack(self._STRUCT_FORMAT_, hdr_only)
        hdr.signature = unpack[0]
        hdr.header_size = unpack[1]
        hdr.total_size = unpack[2]
        hdr.payload_size = unpack[3]
        hdr.action_name = unpack[4]
        hdr.action_kind = unpack[5]
        hdr.chunk_size = unpack[6]
        hdr.chunk_count = unpack[7]
        hdr.chunk_index = unpack[8]
        hdr.length_dirpath = unpack[9]

        # Payload
        hdr.payload = data[hdr_size:]

        # Unpack data from payload
        pos1 = 0
        pos2 = hdr.length_dirpath
        if pos2 - pos1 > 0:
            hdr.dstdirpath = str(hdr.payload[pos1:pos2], 'utf-8')

        pos1 = hdr.length_dirpath
        hdr.data = hdr.payload[pos1:]

        return hdr


class header_execute():
    def __init__(self,
                 kind: action_kind = action_kind.unknown,
                 subcmd: execute_subcmd = execute_subcmd.unknown,
                 program: bytes = b'',
                 argument: bytes = b'',
                 workdir: bytes = b'.',
                 isbase64: bool = False,
                 chunk_data: bytes = b''):

        self._STRUCT_FORMAT_ = '8s' + 'iiiii' + 'iii' + 'iii' + 'Biii'

        #
        # payload_data
        #
        self.cmdresult = execresult()
        self.exec = execmdarg(program, argument, workdir, isbase64)

        #
        # chunk_data
        #
        self.chunk_data = chunk_data  # execresult

        #
        # Header content
        #
        self.signature: bytes = _SIGNATURE_EXECUT_

        self.header_size: int = 0
        self.total_size: int = 0
        self.payload_size: int = 0
        self.action_name: int = action_name.execute.value
        self.action_kind: int = kind.value

        self.subcmd_value: int = 0
        self.status_value: int = proc_status.unknown.value
        self.tag_value = 0

        if subcmd:
            self.subcmd_value = subcmd.value

        self.chunk_size: int = len(chunk_data)
        self.chunk_count: int = 0
        self.chunk_index: int = 0

        if self.chunk_size > 0:
            self.chunk_count = 1

        self.length_isbase64: int = 1
        self.length_program: int = len(program)
        self.length_argument: int = len(argument)
        self.length_workdir: int = len(workdir)

    def pack(self):
        self.header_size = struct.calcsize(self._STRUCT_FORMAT_)
        self.payload_size = (self.length_isbase64 +
                             self.length_program +
                             self.length_argument +
                             self.length_workdir +
                             self.chunk_size)
        self.total_size = self.header_size + self.payload_size

        packed_data = struct.pack(self._STRUCT_FORMAT_,
                                  self.signature,

                                  self.header_size,
                                  self.total_size,
                                  self.payload_size,
                                  self.action_name,
                                  self.action_kind,
                                  self.subcmd_value,
                                  self.status_value,
                                  self.tag_value,

                                  self.chunk_size,
                                  self.chunk_count,
                                  self.chunk_index,

                                  self.length_isbase64,
                                  self.length_program,
                                  self.length_argument,
                                  self.length_workdir)

        isbase = b''
        if self.exec.isbase64:
            isbase = b'1'
        else:
            isbase = b'0'

        data = (isbase +
                self.exec.program +
                self.exec.argument +
                self.exec.workdir +
                self.chunk_data)

        packed_data = packed_data + data

        assert len(packed_data) == self.total_size, 'data lengths are not identical !!!'

        return packed_data

    def unpack(self, chunk_data_raw: bytes):
        packed_data_len = len(chunk_data_raw)
        if packed_data_len <= _HEADER_SIZE_:
            logfmt = '[header_execute] buffer is insufficient !!! (data_len={})'
            logging.info(logfmt.format(packed_data_len))
            return None

        hdr_size: int = int.from_bytes(chunk_data_raw[8:11], 'little')
        total_size: int = int.from_bytes(chunk_data_raw[12:15], 'little')
        logging.info('[header_execute] hdr_size={}'.format(hdr_size))
        logging.info('[header_execute] total_size={}'.format(total_size))

        if packed_data_len < total_size:
            logfmt = '[header_execute] buffer is insufficient !!! ' + \
                     '(data_len={} less than total_size={})'
            logging.info(logfmt.format(packed_data_len, total_size))
            return None

        header_content: bytes = chunk_data_raw[:hdr_size]

        hdr = header_execute()

        # Header files
        unpack = struct.unpack(self._STRUCT_FORMAT_, header_content)
        hdr.signature = unpack[0]
        hdr.header_size = unpack[1]
        hdr.total_size = unpack[2]
        hdr.payload_size = unpack[3]
        hdr.action_name = unpack[4]
        hdr.action_kind = unpack[5]
        hdr.subcmd_value = unpack[6]
        hdr.status_value = unpack[7]
        hdr.tag_value = unpack[8]

        hdr.chunk_size = unpack[9]
        hdr.chunk_count = unpack[10]
        hdr.chunk_index = unpack[11]

        hdr.length_isbase64 = unpack[12]
        hdr.length_program = unpack[13]
        hdr.length_argument = unpack[14]
        hdr.length_workdir = unpack[15]

        #
        # Payload (payload_data + chunk_data)
        #
        payload_content = chunk_data_raw[hdr.header_size: hdr.total_size]

        # Unpack data from payload
        pos1 = 0
        pos2 = (pos1 + 1)
        isbase64 = payload_content[pos1:pos2]
        hdr.exec.isbase64 = bool(int(isbase64))

        pos1 = pos2
        pos2 = pos2 + hdr.length_program
        program = payload_content[pos1:pos2]
        # hdr.program = str(program, encoding='utf-8')
        hdr.exec.program = program

        pos1 = pos2
        pos2 = pos2 + hdr.length_argument
        argument = payload_content[pos1:pos2]
        # hdr.argument = str(argument, encoding='utf-8')
        hdr.exec.argument = argument

        pos1 = pos2
        pos2 = pos2 + hdr.length_workdir
        workdir = payload_content[pos1:pos2]
        # hdr.workdir = str(workdir, 'utf-8')
        hdr.exec.workdir = workdir

        # chunk_data
        pos1 = pos2
        pos2 = pos2 + hdr.chunk_size
        if pos2 - pos1 > 0:
            chunk_data_raw = payload_content[pos1:pos2]
            chunk_data_ori: execresult = config().toCLASS(chunk_data_raw)

            hdr.chunk_data = chunk_data_ori

        return hdr


class header_text():
    def __init__(self, kind: action_kind = action_kind.unknown, title: str = 'default', data: bytes = b''):
        self._STRUCT_FORMAT_ = '8s' + 'iiiii' + 'iii' + 'i'

        #
        # payload_data
        #
        self.title: str = title

        #
        # payload_chunk
        #
        self.payload_chunk = data

        #
        # Header content
        #
        self.signature: bytes = _SIGNATURE_TEXT___

        self.header_size: int = 0
        self.total_size: int = 0
        self.payload_size: int = 0
        self.action_name: int = action_name.text.value
        self.action_kind: int = kind.value

        self.chunk_size: int = len(data)
        self.chunk_count: int = 0
        self.chunk_index: int = 0

        self.length_title: int = len(title)

        if len(data) > 0:
            self.chunk_count = 1

    def pack(self):
        self.header_size = struct.calcsize(self._STRUCT_FORMAT_)
        self.payload_size = self.length_title + self.chunk_size
        self.total_size = self.header_size + self.payload_size

        rawdata = struct.pack(self._STRUCT_FORMAT_,
                              self.signature,

                              self.header_size,
                              self.total_size,
                              self.payload_size,
                              self.action_name,
                              self.action_kind,

                              self.chunk_size,
                              self.chunk_count,
                              self.chunk_index,

                              self.length_title)

        payload = (self.title.encode('ascii') + self.payload_chunk)

        rawdata += payload
        return rawdata

    def unpack(self, data: bytes):
        if len(data) <= _HEADER_SIZE_:
            return None

        hdr_size: int = int.from_bytes(data[8:11], 'little')
        hdr_only: bytes = data[:hdr_size]

        hdr = header_text()

        # Header files
        unpack = struct.unpack(self._STRUCT_FORMAT_, hdr_only)
        hdr.signature = unpack[0]
        hdr.header_size = unpack[1]
        hdr.total_size = unpack[2]
        hdr.payload_size = unpack[3]
        hdr.action_name = unpack[4]
        hdr.action_kind = unpack[5]
        hdr.chunk_size = unpack[6]
        hdr.chunk_count = unpack[7]
        hdr.chunk_index = unpack[8]
        hdr.length_title = unpack[9]

        #
        # Payload
        #
        pos1 = self.header_size
        pos2 = pos1 + self.total_size
        payload = data[pos1:pos2]

        # payload_data
        pos1 = 0
        pos2 = self.length_title
        hdr.title = str(payload[pos1:pos2], encoding='ascii')

        # payload_chunk
        pos1 = pos2
        pos2 = pos1 + self.chunk_size
        hdr.payload_chunk = payload[pos1:pos2]

        return hdr


class header():
    def __init__(self):
        pass

    def find_header(self, data: bytes):
        data_len = len(data)
        if data_len < _HEADER_SIZE_:
            logging.info('buffer is insufficient !!! (data_len={})'.format(data_len))
            return None, 0

        index = 0
        matched_index = -1
        targets = [_SIGNATURE_UPLOAD_,  # 0
                   _SIGNATURE_DOWNLO_,  # 1
                   _SIGNATURE_EXECUT_,  # 2
                   _SIGNATURE_LIST___,  # 3
                   _SIGNATURE_ECHO___,  # 4
                   _SIGNATURE_TEXT___]  # 5

        signature_pos = -1
        for item in targets:
            signature_pos = data.find(item)
            if signature_pos >= 0:
                matched_index = index
                logging.info('signature matched (matched_index={}).'.format(matched_index))
                break
            index += 1

        hdr_pos1 = signature_pos + 8
        hdr_pos2 = hdr_pos1 + 4
        header_size: int = int.from_bytes(data[hdr_pos1:hdr_pos2], 'little')
        if data_len < header_size:
            logging.info('buffer is insufficient !!! (data_len is less than header_size)')
            return None, 0

        found_hdr = None
        hdr_pos1 = signature_pos + 12
        hdr_pos2 = hdr_pos1 + 4
        total_size: int = int.from_bytes(data[hdr_pos1:hdr_pos2], 'little')
        if data_len < total_size:
            logging.info('buffer is insufficient !!! (data_len is less than total_size)')
            return None, 0

        chunk_end_pos = signature_pos + total_size
        chunk_diff = chunk_end_pos - signature_pos
        logging.info('total_size={}'.format(signature_pos))
        logging.info('chunk_end_pos={}'.format(chunk_end_pos))
        logging.info('chunk_end_pos-signature_pos={}'.format(chunk_diff))
        full_header = data[signature_pos:chunk_end_pos]
        full_header_size = len(full_header)
        logging.info('full_header_size={}'.format(full_header_size))

        if 0 == matched_index:
            logging.info('unpacking header_upload ...')

            hdr: header_upload = header_upload().unpack(full_header)
            logging.info('find a header_upload')
            if hdr is None:
                logging.warning('buffer is insufficient !!! (failed to unpack)')
                return None, 0

            hdr_pos1 = 0
            hdr_pos2 = hdr_pos1 + hdr.total_size
            if len(data) >= hdr_pos2:
                # full_header = data[hdr_pos1:hdr_pos2]
                found_hdr = hdr.unpack(full_header)
                logging.info('unpack a header_upload, len(chunk)={}'.format(len(full_header)))

                logfmt = 'header_upload action_kind={} chunk_index={}/{} ' + \
                         'chunk_size={}'
                logging.info(logfmt.format(found_hdr.action_kind,
                                           found_hdr.chunk_index + 1,
                                           found_hdr.chunk_count,
                                           found_hdr.chunk_size))

                logging.info('filename={}'.format(found_hdr.filename))
                logging.info('dstdirpath={}'.format(found_hdr.dstdirpath))
                logging.info('file_size={}'.format(found_hdr.file_size))

            else:
                logging.warning('buffer is insufficient for a header_upload, len(data)={}'.format(len(data)))
                found_hdr = None
                hdr_pos2 = 0

        elif 1 == matched_index:
            logging.info('unpacking header_download ...')

            hdr: header_download = header_download().unpack(full_header)
            if hdr is None:
                logging.warning('buffer is insufficient !!! (failed to unpack)')
                return None, 0

            hdr_pos1 = 0
            hdr_pos2 = hdr_pos1 + hdr.total_size
            if len(full_header) >= hdr_pos2:
                found_hdr: header_download = hdr.unpack(full_header)
                logging.info('unpack a header_download, len(chunk)={}'.format(len(full_header)))

                logfmt = 'header_download action_kind={} chunk_index={}/{} ' + \
                         'chunk_size={}'
                logging.info(logfmt.format(found_hdr.action_kind,
                                           found_hdr.chunk_index + 1,
                                           found_hdr.chunk_count,
                                           found_hdr.chunk_size))
                logging.info('filepath={}'.format(found_hdr.filepath))
                logging.info('file_size={}'.format(found_hdr.file_size))

            else:
                logging.warning('buffer is insufficient for a header_download, len(data)={}'.format(len(data)))
                found_hdr = None
                hdr_pos2 = 0

        elif 2 == matched_index:
            logging.info('unpacking header_execute ...')

            hdr: header_execute = header_execute().unpack(full_header)
            if hdr is None:
                logging.warning('buffer is insufficient !!! (failed to unpack)')
                return None, 0

            hdr_pos1 = 0
            hdr_pos2 = hdr_pos1 + hdr.total_size
            if len(full_header) >= hdr_pos2:
                found_hdr: header_execute = hdr.unpack(full_header)
                logging.info('unpack a header_execute, len(chunk)={}'.format(len(full_header)))

                logfmt = 'header_execute action_kind={} chunk_index={}/{} ' + \
                         'chunk_size={}'
                logging.info(logfmt.format(found_hdr.action_kind,
                                           found_hdr.chunk_index + 1,
                                           found_hdr.chunk_count,
                                           found_hdr.chunk_size))

                logging.info('program={}'.format(found_hdr.exec.program))
                logging.info('argument={}'.format(found_hdr.exec.argument))
                logging.info('workdir={}'.format(found_hdr.exec.workdir))

            else:
                logging.warning('buffer is insufficient for a header_execute, len(data)={}'.format(len(data)))
                found_hdr = None
                hdr_pos2 = 0

        elif 3 == matched_index:
            logging.info('unpacking header_list ...')

            hdr: header_list = header_list().unpack(full_header)
            if hdr is None:
                logging.warning('buffer is insufficient !!! (failed to unpack)')
                return None, 0

            hdr_pos1 = 0
            hdr_pos2 = hdr_pos1 + hdr.total_size
            if len(full_header) >= hdr_pos2:
                # full_header = full_header[hdr_pos1:hdr_pos2]
                found_hdr = hdr.unpack(full_header)
                logging.info('unpack a header_list, len(chunk)={}'.format(len(full_header)))

                logfmt = 'header_list action_kind={} chunk_index={}/{} ' + \
                         'chunk_size={}'
                logging.info(logfmt.format(found_hdr.action_kind,
                                           found_hdr.chunk_index + 1,
                                           found_hdr.chunk_count,
                                           found_hdr.chunk_size))

                logging.info('dstdirpath={}'.format(found_hdr.dstdirpath))

            else:
                logging.warning('buffer is insufficient for a header_list, len(data)={}'.format(len(data)))
                found_hdr = None
                hdr_pos2 = 0

        elif 4 == matched_index:
            logging.info('unpacking header_echo ...')

            hdr: header_echo = header_echo().unpack(full_header)
            if hdr is None:
                logging.warning('buffer is insufficient !!! (failed to unpack)')
                return None, 0

            hdr_pos1 = 0
            hdr_pos2 = hdr_pos1 + hdr.total_size
            if len(full_header) >= hdr_pos2:
                # full_header = full_header[hdr_pos1:hdr_pos2]
                found_hdr = hdr.unpack(full_header)
                logging.info('unpack a header_echo, len(chunk)={}'.format(len(full_header)))

                logfmt = 'header_echo action_kind={} chunk_index={}/{} ' + \
                         'chunk_size={}'
                logging.info(logfmt.format(found_hdr.action_kind,
                                           found_hdr.chunk_index + 1,
                                           found_hdr.chunk_count,
                                           found_hdr.chunk_size))
            else:
                logging.warning('buffer is insufficient for a header_echo, len(data)={}'.format(len(data)))
                found_hdr = None
                hdr_pos2 = 0

        elif 5 == matched_index:
            logging.info('unpacking header_text ...')

            hdr: header_text = header_text().unpack(full_header)
            if hdr is None:
                logging.warning('buffer is insufficient !!! (failed to unpack)')
                return None, 0

            hdr_pos1 = 0
            hdr_pos2 = hdr_pos1 + hdr.total_size
            if len(full_header) >= hdr_pos2:
                found_hdr = hdr.unpack(full_header)
                logging.info('unpack a header_text, len(chunk)={}'.format(len(full_header)))

                logfmt = 'header_text action_kind={} chunk_index={}/{} ' + \
                         'chunk_size={}'
                logging.info(logfmt.format(found_hdr.action_kind,
                                           found_hdr.chunk_index + 1,
                                           found_hdr.chunk_count,
                                           found_hdr.chunk_size))
            else:
                logging.warning('buffer is insufficient for a header_text, len(data)={}'.format(len(data)))
                found_hdr = None
                hdr_pos2 = 0

        else:
            logging.warning('buffer missed matching, len(data)={}'.format(len(data)))
            found_hdr = None
            hdr_pos2 = 0

        return found_hdr, hdr_pos2


class actor_callbacks():
    def __init__(self):
        self.list = None
        self.upload = None
        self.download = None
        self.execute = None
        self.text = None


class rcsock():

    def __init__(self, conn, actors: actor_callbacks = None):
        self.BUFF_SIZE = _BUFFER_SIZE_

        self.header = header()
        self.conn: socket.socket = conn
        self.stream_pool = b''
        self.chunk_list = list()
        self.server_callback = actors
        self.file_path = ''
        self.file_handle = None

        self.conn.setblocking(True)

        self.thread = threading.Thread(target=self._receive_stream)
        self.thread.daemon = True
        self.thread.start()

    def _send(self, data):

        data_len = len(data)
        logging.info('data_len={}'.format(data_len))

        ret = None
        try:
            ret = self.conn.sendall(data)

        except Exception as Err:
            logging.exception(Err)

        finally:
            return ret

    def _wait_until(self, condition, interval=0.1, timeout=1, *args):
        start = time.time()
        while not condition(*args) and time.time() - start < timeout:
            time.sleep(interval)
        return condition(*args)

    def _receive_stream(self):

        try:
            while chunk := self.conn.recv(self.BUFF_SIZE):
                chunklen = len(chunk)
                logging.info('chunklen={}'.format(chunklen))

                self.stream_pool += chunk
                self._parse_complete_chunk()

                if self.server_callback:
                    self._consume_chunks()

        except socket.timeout:
            logging.exception('socket.timeout')

        except ConnectionResetError:
            logging.warning('ConnectionResetError')

        except Exception as Err:
            print(Err)
            logging.exception(Err)

        finally:
            pass

    def _consume_chunks(self):

        while len(self.chunk_list) > 0:
            logging.info('There are {} chunk in the chunk_list.'.format(
                         len(self.chunk_list)))

            chunk = self.chunk_list.pop(0)
            logfmt = 'action_kind={} chunk_index={}/{} chunk_size={}'
            logging.info(logfmt.format(chunk.action_kind,
                                       chunk.chunk_index + 1,
                                       chunk.chunk_count,
                                       chunk.chunk_size))

            if chunk.action_name == action_name.list.value:
                # def _handle_list_command(self,
                #                          conn: socket.socket,
                #                          hdr: header_list):
                self.server_callback.list(self, chunk)

            elif chunk.action_name == action_name.upload.value:
                # def _handle_upload_command(self,
                #                            sock: rcsock,
                #                            hdr: header_upload,
                #                            overwrite: bool = True):
                self.server_callback.upload(self, chunk)

            elif chunk.action_name == action_name.download.value:
                # def _handle_download_command(self,
                #                              conn: rcsock,
                #                              data_hdr: header_download):
                self.server_callback.download(self, chunk)

            elif chunk.action_name == action_name.execute.value:
                # def _handle_execute_command(self,
                #                             sock: rcsock,
                #                             ask_chunk: header_execute):
                self.server_callback.execute(self, chunk)

            elif chunk.action_name == action_name.text.value:
                # def _handle_text_command(self,
                #                          sock: rcsock,
                #                          ask_chunk: header_text):
                self.server_callback.text(self, chunk)

            else:
                pass

    def _parse_complete_chunk(self):
        while True:

            logfmt = 'b4 len(self.stream_pool)={}'
            logging.info(logfmt.format(len(self.stream_pool)))

            logfmt = 'b4 len(self.chunk_list)={}'
            logging.info(logfmt.format(len(self.chunk_list)))

            found_header, size = self.header.find_header(self.stream_pool)
            if 0 == size:
                logging.info('Nothing found !!!')
                break

            logging.info('Found a new header, ' +
                         'will be insertted to chunk_list.')
            self.chunk_list.append(found_header)
            self.stream_pool = self.stream_pool[size:]

            logfmt = 'ft len(self.stream_pool)={}'
            logging.info(logfmt.format(len(self.stream_pool)))

            logfmt = 'ft len(self.chunk_list)={}'
            logging.info(logfmt.format(len(self.chunk_list)))


class rcserver():
    def __init__(self, host: str, port: int, workdir: str = '~',
                 debug_enabled: bool = False):

        self.CHUNK_SIZE = _CHUNK_SIZE_
        self.client_list = list()
        self.chunk_list = list()
        self.stream_pool = b''

        self.proc_list = list()

        self.server_callback = actor_callbacks()
        self.server_callback.download = self._handle_download_command
        self.server_callback.list = self._handle_list_command
        self.server_callback.upload = self._handle_upload_command
        self.server_callback.execute = self._handle_execute_command
        self.server_callback.text = self._handle_text_command

        self.__HOST__ = host
        self.__PORT__ = port
        self.__WORKDIR__ = workdir

        if debug_enabled:
            self._enable_debug()

    def _enable_debug(self):
        prefix = '[%(asctime)s][%(levelname)s]' + \
                 '[%(filename)s!%(funcName)s:%(lineno)d] %(message)s'
        format = logging.Formatter(prefix, datefmt='%Y%m%d %H:%M:%S')
        logger = logging.getLogger()

        # Write to file
        logfile = logging.FileHandler('rcserver.log')
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(format)
        logger.addHandler(logfile)

        # # Write to screen
        # screen = logging.StreamHandler()
        # screen.setLevel(logging.INFO)
        # screen.setFormatter(format)
        # logger.addHandler(screen)

    def start(self):
        self._listening = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.__PORT__))
        self.sock.listen(10)

        try:
            while self._listening:
                conn, _ = self.sock.accept()
                conn.sendall(header_echo().pack())
                self.client_list.append(rcsock(conn, self.server_callback))

        except Exception as e:
            logging.exception(e)

        finally:
            self.sock.close()

    def stop(self):
        self._listening = False
        for client in self.client_list:
            client: rcsock = client
            client.conn.close()

    def get_addr_info(self):
        return (self.__HOST__, self.__PORT__)

    def _handle_list_command(self, conn: rcsock, ask_chunk: header_list):

        logging.info('-------------------------------------------')
        filepath = os.path.abspath(ask_chunk.dstdirpath)

        logfmt = 'filepath={}'
        logging.info(logfmt.format(filepath))

        if not os.path.exists(filepath):
            return error_file_not_found

        listdir = []
        if os.path.isdir(filepath):
            listdir = os.listdir(filepath)
        else:
            listdir.append(os.path.basename(filepath))

        index = 0
        for file in listdir:
            index += 1
            logging.info('file[{}/{}]={}'.format(index, len(listdir), file))

        data = json.dumps(listdir).encode()
        data_chunk = header_list(action_kind.data,
                                 filepath,
                                 data)
        data_chunk.chunk_count = 1
        data_chunk.chunk_index = 0
        data_chunk.chunk_size = len(data)
        conn._send(data_chunk.pack())

        # done_chunk = header_list(action_kind.done, ask_chunk.dstdirpath)
        # conn._send(done_chunk.pack())

        return True

    def _handle_download_command(self,
                                 conn: rcsock,
                                 ask_chunk: header_download):

        logging.info('-------------------------------------------')
        fileloc = os.path.abspath(ask_chunk.filepath)
        logging.info("fileloc={}".format(fileloc))

        rcrs = rcresult()
        # if ask_chunk.action_kind == action_kind.done.value:
        #     return rcrs

        if not os.path.exists(fileloc):
            logging.error("The spcific path is not found !!!")
            logging.error("fileloc={}".format(fileloc))
            rcrs = error_file_not_found

        if os.path.isdir(fileloc):
            logging.error("The spcific path should be a file !!!")
            logging.error("fileloc={}".format(fileloc))
            rcrs = error_not_a_file

        # data + done for error
        if 0 != rcrs.errcode:
            data_chunk = header_download(action_kind.data,
                                         ask_chunk.filepath,
                                         ask_chunk.file_size)
            conn._send(data_chunk.pack())

            done_chunk = header_download(action_kind.done,
                                         ask_chunk.filepath,
                                         ask_chunk.file_size)
            conn._send(done_chunk.pack())
            return rcrs

        filesize = os.path.getsize(fileloc)

        index = 0
        chunk_count = int(filesize / self.CHUNK_SIZE)
        if (filesize % self.CHUNK_SIZE) > 0:
            chunk_count += 1

        # data
        file = open(fileloc, "rb")
        while data := file.read(self.CHUNK_SIZE):

            datalen = len(data)
            logging.info('chunklen={}'.format(datalen))

            data_chunk = header_download(action_kind.data,
                                         ask_chunk.filepath,
                                         filesize,
                                         data)
            data_chunk.chunk_size = min(self.CHUNK_SIZE, datalen)
            data_chunk.chunk_count = chunk_count
            data_chunk.chunk_index = index

            logfmt = 'header_download action_kind={} chunk_index={}/{} ' + \
                     'chunk_size={}'
            logging.info(logfmt.format(data_chunk.action_kind,
                                       data_chunk.chunk_index + 1,
                                       data_chunk.chunk_count,
                                       data_chunk.chunk_size))

            conn._send(data_chunk.pack())
            index += 1

        file.close()

        # done by complete
        done_chunk = header_download(action_kind.done,
                                     ask_chunk.filepath,
                                     filesize)
        conn._send(done_chunk.pack())

        return True

    def _handle_upload_command(self,
                               sock: rcsock,
                               data_chunk: header_upload,
                               overwrite: bool = True):

        logging.info('-------------------------------------------')
        logfmt = 'chunk_index={}/{} file_size={} chunk_size={}'
        logging.info(logfmt.format(data_chunk.chunk_index + 1,
                                   data_chunk.chunk_count,
                                   data_chunk.file_size,
                                   data_chunk.chunk_size))
        try:
            # open
            if not sock.file_handle and \
               data_chunk.action_kind == action_kind.ask.value:
                filepath = os.path.join(data_chunk.dstdirpath,
                                        data_chunk.filename)
                fullpath = os.path.abspath(filepath)
                logging.info('open file (fullpath={})'.format(fullpath))
                sock.file_path = filepath
                sock.file_handle = open(filepath, "wb")

            # write
            if data_chunk.action_kind == action_kind.data.value:
                sock.file_handle.write(data_chunk.data)

                diff = (data_chunk.chunk_count - data_chunk.chunk_index)
                is_last_data = (1 == diff)
                logging.info('last_chunk={}'.format(is_last_data))
                logging.info('filepath={}'.format(sock.file_path))

            # close
            if data_chunk.action_kind == action_kind.done.value:
                if sock.file_handle:
                    logfmt = 'close file (fullpath={})'
                    logging.info(logfmt.format(sock.file_path))
                    sock.file_handle.flush()
                    sock.file_handle.close()
                    sock.file_handle = None
                    sock.file_path = ''

                    # done (reply)
                    chunk_done = header_upload(action_kind.done,
                                               data_chunk.filename,
                                               data_chunk.file_size,
                                               data_chunk.dstdirpath)
                    sock._send(chunk_done.pack())

        except Exception as err:
            logging.exception(err)

        return True

    def _handle_execute_command(self,
                                sock: rcsock,
                                ask_chunk: header_execute):
        try:
            data_chunk = None

            logging.info('-------------------------------------------')
            logging.info('[UTF8] program={}'.format(ask_chunk.exec.program))
            logging.info('[UTF8] argument={}'.format(ask_chunk.exec.argument))
            logging.info('[UTF8] workdir={}'.format(ask_chunk.exec.workdir))

            program = str(ask_chunk.exec.program, encoding='utf-8')

            argument = ''
            if ask_chunk.exec.isbase64:
                argument = base64.b64decode(ask_chunk.exec.argument).decode('utf-8')
            else:
                argument = str(ask_chunk.exec.argument, encoding='utf-8')

            workdir = str(ask_chunk.exec.workdir, encoding='utf-8')

            logging.info('[ORIGIN] program={}'.format(program))
            logging.info('[ORIGIN] argument={}'.format(argument))
            logging.info('[ORIGIN] workdir={}'.format(workdir))

            # subcmd: start
            if ask_chunk.subcmd_value == execute_subcmd.start.value:
                logging.info('Before opening a process')
                async_proc = async_process(len(self.proc_list) + 100)
                self.proc_list.append(async_proc)

                async_proc.run(program, argument, workdir)
                logging.info('After opening a process')

                subcmd = execute_subcmd(ask_chunk.subcmd_value)
                data_chunk = header_execute(action_kind.data,
                                            subcmd,
                                            ask_chunk.exec.program,
                                            ask_chunk.exec.argument,
                                            ask_chunk.exec.workdir,
                                            ask_chunk.exec.isbase64)
                data_chunk.status_value = async_proc.get_status().value
                data_chunk.tag_value = async_proc.get_tag()

            # subcmd: kill
            elif ask_chunk.subcmd_value == execute_subcmd.kill.value:
                subcmd = execute_subcmd(ask_chunk.subcmd_value)
                data_chunk = header_execute(action_kind.data,
                                            subcmd,
                                            ask_chunk.exec.program,
                                            ask_chunk.exec.argument,
                                            ask_chunk.exec.workdir,
                                            ask_chunk.exec.isbase64)
                data_chunk.status_value = proc_status.killing
                for item in self.proc_list:
                    item: async_process = item
                    if item.get_tag() == ask_chunk.tag_value:
                        item.kill()
                        data_chunk.status_value = item.get_status()
                        data_chunk.tag_value = ask_chunk.tag_value

            # subcmd: query
            elif ask_chunk.subcmd_value == execute_subcmd.query.value:
                data = b''
                status = proc_status.unknown

                for item in self.proc_list:
                    item: async_process = item
                    if item.get_tag() == ask_chunk.tag_value:
                        status = item.get_status()
                        data = item.execrs.toTEXT().encode()
                        break

                subcmd = execute_subcmd(ask_chunk.subcmd_value)
                data_chunk = header_execute(action_kind.data,
                                            subcmd,
                                            ask_chunk.exec.program,
                                            ask_chunk.exec.argument,
                                            ask_chunk.exec.workdir,
                                            ask_chunk.exec.isbase64,
                                            data)
                data_chunk.tag_value = ask_chunk.tag_value
                data_chunk.status_value = status.value

            else:
                subcmd = execute_subcmd(ask_chunk.subcmd_value)
                data_chunk = header_execute(action_kind.data,
                                            subcmd,
                                            ask_chunk.exec.program,
                                            ask_chunk.exec.argument,
                                            ask_chunk.exec.workdir,
                                            ask_chunk.exec.isbase64)
                data_chunk.tag_value = ask_chunk.tag_value
                data_chunk.status_value = proc_status.exception

        except Exception as Err:
            logging.exception(Err)
            subcmd = execute_subcmd(ask_chunk.subcmd_value)
            data_chunk = header_execute(action_kind.data,
                                        subcmd,
                                        ask_chunk.exec.program,
                                        ask_chunk.exec.argument,
                                        ask_chunk.exec.workdir)
            data_chunk.tag_value = ask_chunk.tag_value
            data_chunk.status_value = proc_status.exception

        finally:
            # send data
            packed_data_chunk = data_chunk.pack()
            sock._send(packed_data_chunk)
            logging.info('send data ({})'.format(ask_chunk.exec.program))

            # send done
            subcmd = execute_subcmd(ask_chunk.subcmd_value)
            done_chunk = header_execute(action_kind.done,
                                        subcmd,
                                        ask_chunk.exec.program,
                                        ask_chunk.exec.argument,
                                        ask_chunk.exec.workdir)
            done_chunk.tag_value = data_chunk.tag_value
            logging.info('send done ({})'.format(ask_chunk.exec.program))
            sock._send(done_chunk.pack())

    def _handle_text_command(self,
                             sock: rcsock,
                             ask_chunk: header_text):

        logging.info('-------------------------------------------')
        logging.info('title={}'.format(ask_chunk.title))

        data = None

        if 'default' == ask_chunk.title:
            data = 'Hello from server with default'.encode()

        elif 'computer_info' == ask_chunk.title:
            osname = platform.system().lower()
            homedir = os.path.expanduser('~')
            data = computer_info(osname, homedir).toTEXT().encode()
            done_chunk = header_text(action_kind.done, ask_chunk.title, data)
            sock._send(done_chunk.pack())

        elif 'inncmd_mkdir' == ask_chunk.title:
            result: bool = True

            path = str(ask_chunk.payload_chunk, encoding='utf-8')
            try:
                pos1 = path.find('/')
                pos2 = path.find('\\')
                if pos1 >= 0 or pos2 >= 0:
                    os.makedirs(path)
                else:
                    os.mkdir(path)

            except Exception as Err:
                logging.error(Err)
                result = False

            data = inncmd_mkdir(path, result).toTEXT().encode()
            done_chunk = header_text(action_kind.done, ask_chunk.title, data)
            sock._send(done_chunk.pack())

        else:
            data = 'Hello from server with UNKNOWN'.encode()
            done_chunk = header_text(action_kind.done, ask_chunk.title, data)
            sock._send(done_chunk.pack())

        return True


class rcclient():

    def __init__(self):
        self.CHUNK_SIZE = _CHUNK_SIZE_
        self.BUFF_SIZE = _BUFFER_SIZE_
        self.TIMEOUT_TIMES = 10

        self.__HOST__ = None
        self.__PORT__ = 0

        self.sock = None
        self._connected = False

    def _wait_until(self, condition, interval=0.1, timeout=1, *args):
        start = time.time()
        while not condition(*args) and time.time() - start < timeout:
            time.sleep(interval)
        return condition(*args)

    def connect(self, host: str, port: int):
        self.__HOST__ = host
        self.__PORT__ = port
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ret = conn.connect_ex((self.__HOST__, self.__PORT__))

        if ret:
            self._connected = False
        else:
            chunk = conn.recv(self.BUFF_SIZE)
            echo_chunk = header_echo().unpack(chunk)

            try:
                if (echo_chunk.signature[0] == _SIGNATURE_ECHO___[0]) and \
                   (echo_chunk.signature[1] == _SIGNATURE_ECHO___[1]) and \
                   (echo_chunk.signature[2] == _SIGNATURE_ECHO___[2]) and \
                   (echo_chunk.signature[3] == _SIGNATURE_ECHO___[3]) and \
                   (echo_chunk.signature[4] == _SIGNATURE_ECHO___[4]) and \
                   (echo_chunk.signature[5] == _SIGNATURE_ECHO___[5]) and \
                   (echo_chunk.signature[6] == _SIGNATURE_ECHO___[6]) and \
                   (echo_chunk.signature[7] == _SIGNATURE_ECHO___[7]):
                    self._connected = True
                    conn.setblocking(True)
                    self.sock = rcsock(conn)

            except Exception:
                self._connected = False
                logging.error('Failed to receive an ECHO from server !!!')

        return self._connected

    def is_connected(self):
        return self._connected

    def stop(self):
        self._connected = False

    def _send(self, data):
        self.sock._send(data)

    def _execute_start(self, cmdarg: execmdarg):
        execrs = execresult()

        ask_chunk = header_execute(action_kind.ask,
                                   execute_subcmd.start,
                                   cmdarg.program,
                                   cmdarg.argument,
                                   cmdarg.workdir,
                                   cmdarg.isbase64)
        self._send(ask_chunk.pack())

        # wait data
        logging.info('wait data ({})'.format(ask_chunk.exec.program))
        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        logging.info('is_there_a_chunk={}'.format(is_there_a_chunk))
        if not is_there_a_chunk:
            program = ask_chunk.exec.program
            logging.error('wait data timeout !!! ({})'.format(program))
            execrs.errcode = error_wait_timeout_streaming.errcode
            execrs.stderr.append(error_wait_timeout_streaming.text)

        else:
            program = ask_chunk.exec.program
            logging.info('fetch the data ({})'.format(program))
            chunk: header_execute = self.sock.chunk_list.pop(0)
            logging.info('chunk.data={}'.format(str(chunk.chunk_data)))

        # wait done
        logging.info('wait done ({})'.format(ask_chunk.exec.program))
        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        logging.info('is_there_a_chunk={}'.format(is_there_a_chunk))
        if not is_there_a_chunk:
            program = ask_chunk.exec.program
            logging.error('wait done timeout !!! ({})'.format(program))
            execrs.errcode = error_wait_timeout_streaming.errcode
            execrs.stderr.append(error_wait_timeout_streaming.text)

        else:
            program = ask_chunk.exec.program
            logging.info('fetch the done ({})'.format(program))
            chunk: header_execute = self.sock.chunk_list.pop(0)
            execrs.data = chunk.tag_value

        return execrs

    def _execute_query(self, cmdarg: execmdarg, proc_tag: int):

        retry_times = 3
        while retry_times > 0:
            execrs, status = self._execute_query_and_wait(cmdarg, proc_tag)
            if status != proc_status.running:
                break
            time.sleep(2)

        return execrs

    def _execute_query_and_wait(self, cmdarg: execmdarg, proc_tag: int):
        ask_chunk = header_execute(action_kind.ask,
                                   execute_subcmd.query,
                                   cmdarg.program,
                                   cmdarg.argument,
                                   cmdarg.workdir,
                                   cmdarg.isbase64)
        execrs = execresult()
        status = proc_status.unknown

        ask_chunk.tag_value = proc_tag
        self._send(ask_chunk.pack())

        # wait data
        logging.info('wait data ({})'.format(ask_chunk.exec.program))
        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        logging.info('is_there_a_chunk={}'.format(is_there_a_chunk))
        if not is_there_a_chunk:
            program = ask_chunk.exec.program
            logging.error('wait data timeout !!! ({})'.format(program))
            execrs.errcode = error_wait_timeout_streaming.errcode
            execrs.stderr.append(error_wait_timeout_streaming.text)

        else:
            program = ask_chunk.exec.program
            logging.info('fetch the data ({})'.format(program))
            chunk: header_execute = self.sock.chunk_list.pop(0)
            logging.info('chunk.data={}'.format(str(chunk.chunk_data)))

            if chunk.chunk_data:
                execrs = chunk.chunk_data
                status = proc_status(chunk.status_value)

        # wait done
        logging.info('wait done ({})'.format(ask_chunk.exec.program))
        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        logging.info('is_there_a_chunk={}'.format(is_there_a_chunk))
        if not is_there_a_chunk:
            program = ask_chunk.exec.program
            logging.error('wait done timeout !!! ({})'.format(program))
            execrs.errcode = error_wait_timeout_streaming.errcode
            execrs.stderr.append(error_wait_timeout_streaming.text)

        else:
            program = ask_chunk.exec.program
            logging.info('fetch the done ({})'.format(program))
            chunk: header_execute = self.sock.chunk_list.pop(0)

        return execrs, status

    def _execute_kill(self, cmdarg: execmdarg, proc_tag: int):
        ask_chunk = header_execute(action_kind.ask,
                                   execute_subcmd.kill,
                                   cmdarg.program,
                                   cmdarg.argument,
                                   cmdarg.workdir,
                                   cmdarg.isbase64)
        execrs = execresult()

        ask_chunk.tag_value = proc_tag
        self._send(ask_chunk.pack())

        # wait data
        logging.info('wait data ({})'.format(ask_chunk.exec.program))
        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        logging.info('is_there_a_chunk={}'.format(is_there_a_chunk))
        if not is_there_a_chunk:
            program = ask_chunk.exec.program
            logging.error('wait data timeout !!! ({})'.format(program))
            execrs.errcode = error_wait_timeout_streaming.errcode
            execrs.stderr.append(error_wait_timeout_streaming.text)

        else:
            program = ask_chunk.exec.program
            logging.info('fetch the data ({})'.format(program))
            chunk: header_execute = self.sock.chunk_list.pop(0)
            logging.info('chunk.data={}'.format(str(chunk.chunk_data)))

            if chunk.chunk_data:
                execrs = chunk.chunk_data

        # wait done
        logging.info('wait done ({})'.format(ask_chunk.exec.program))
        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        logging.info('is_there_a_chunk={}'.format(is_there_a_chunk))
        if not is_there_a_chunk:
            program = ask_chunk.exec.program
            logging.error('wait done timeout !!! ({})'.format(program))
            execrs.errcode = error_wait_timeout_streaming.errcode
            execrs.stderr.append(error_wait_timeout_streaming.text)

        else:
            program = ask_chunk.exec.program
            logging.info('fetch the done ({})'.format(program))
            chunk: header_execute = self.sock.chunk_list.pop(0)

        return result

    def upload(self, local_filepath: str, remote_dirpath: str = '.'):

        filepath = os.path.abspath(local_filepath)
        if not os.path.exists(filepath):
            return error_path_not_exist

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)

        # ask
        hdr = header_upload(action_kind.ask,
                            filename,
                            filesize,
                            remote_dirpath)

        self._send(hdr.pack())

        logging.info('filename={}'.format(filename))
        logging.info('filesize={}'.format(filesize))
        logging.info('filepath={}'.format(filepath))

        index = 0
        sentsize = 0
        chunk_count = int(filesize / self.CHUNK_SIZE)
        if filesize % self.CHUNK_SIZE > 0:
            chunk_count += 1

        # data
        file = open(filepath, "rb")
        while data := file.read(self.CHUNK_SIZE):
            hdr = header_upload(action_kind.data,
                                filename,
                                filesize,
                                remote_dirpath,
                                data)

            hdr.chunk_size = min(self.CHUNK_SIZE, len(data))
            hdr.chunk_index = index
            hdr.chunk_count = chunk_count

            self._send(hdr.pack())

            index += 1
            sentsize += hdr.chunk_size
            logging.info('index={}/{} size={} sentsize={} name={}'.format(
                hdr.chunk_index + 1,
                hdr.chunk_count,
                hdr.chunk_size,
                sentsize,
                hdr.filename))

        file.close()

        # done
        hdr = header_upload(action_kind.done,
                            filename,
                            filesize,
                            remote_dirpath)
        self._send(hdr.pack())

        wait_done = self._wait_until(len,
                                     0.1,
                                     _WAIT_TIMEOUT_,
                                     self.sock.chunk_list)
        if wait_done:
            self.sock.chunk_list.pop(0)
        else:
            return error_wait_timeout_done

        return rcresult()

    def download(self, remote_filepath: str, local_dirpath: str,
                 overwrite: bool = True):

        # if not os.path.exists(remote_filepath):
        #     return error_file_not_found

        if not os.path.exists(local_dirpath):
            return error_path_not_exist

        filepath = remote_filepath
        filename = os.path.basename(filepath)
        fileloc = os.path.join(local_dirpath, filename)
        logging.info('filepath={}'.format(filepath))
        logging.info('filename={}'.format(filename))
        logging.info('fileloc={}'.format(fileloc))

        if (not overwrite) and os.path.exists(fileloc):
            return error_file_already_exist

        hdr = header_download(action_kind.ask, remote_filepath)
        self._send(hdr.pack())

        filepath_dst = os.path.join(local_dirpath, filename)
        logging.info('filepath_dst={}'.format(filepath_dst))

        index = 0
        recvsize = 0
        result = rcresult()

        keep_going = True

        file_size = 0
        file = None
        while keep_going:
            is_there_a_chunk = self._wait_until(len,
                                                0.1,
                                                _WAIT_TIMEOUT_,
                                                self.sock.chunk_list)
            if not is_there_a_chunk:
                result = error_wait_timeout_streaming
                break

            while len(self.sock.chunk_list) > 0:
                is_data_chunk = self.sock.chunk_list[0].action_kind == action_kind.data.value

                # unexpected case because no chunk in the list
                if not is_data_chunk:
                    keep_going = False
                    break

                data_chunk: header_download = self.sock.chunk_list.pop(0)
                file_size = data_chunk.file_size

                # unexpected data_chunk with zero-size chunk
                if 0 == data_chunk.chunk_size:
                    result = error_file_not_found
                    keep_going = False
                    break

                if not file:
                    file = open(filepath_dst, "wb")

                file.write(data_chunk.data)

                index += 1
                recvsize += data_chunk.chunk_size

                logging.info('index={}/{} size={} recvsize={} name={}'.format(
                    hdr.chunk_index + 1,
                    hdr.chunk_count,
                    hdr.chunk_size,
                    recvsize,
                    hdr.filepath))

            if recvsize == file_size:
                break

        if file:
            file.flush()
            file.close()
            file = False

        # wait done
        wait_done = self._wait_until(len,
                                     0.1,
                                     _WAIT_TIMEOUT_,
                                     self.sock.chunk_list)
        if wait_done:
            self.sock.chunk_list.pop(0)
        else:
            return error_wait_timeout_done

        return result

    def list(self, dstdirpath: str):

        ask_chunk = header_list(action_kind.ask, dstdirpath)
        self._send(ask_chunk.pack())

        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        if is_there_a_chunk:
            result = rcresult()

            data_chunk: header_list = self.sock.chunk_list.pop(0)
            result.data = json.loads(data_chunk.data)

            logging.info('type(result.data) = {}'.format(type(result.data)))
            logging.info('result.data = {}'.format(result.data))

            index = 0
            total = len(result.data)
            for file in result.data:
                index += 1
                logfmt = 'file[{}/{}]={}'
                logging.info(logfmt.format(index, total, file))

            return result
        else:
            return error_wait_timeout_streaming

    def execute(self,
                program: str,
                argument: str = '',
                workdir: str = '.',
                isbase64: bool = False):

        argument_encoded = b''
        if isbase64:
            argument_encoded = argument.encode('ascii')
        else:
            argument_encoded = argument.encode('utf-8')

        result = rcresult()
        proc_tag = 0

        cmdarg = execmdarg(program.encode('utf-8'),
                           argument_encoded,
                           workdir.encode('utf-8'),
                           isbase64)
        cmdrs = self._execute_start(cmdarg)

        result.data = cmdrs
        if 0 != cmdrs.errcode:
            result.errcode = cmdrs.errcode
            result.text = '\n'.join(cmdrs.stderr)

        else:
            proc_tag = cmdrs.data

        if 0 == proc_tag:
            result.errcode = -1
            result.text = 'failed to run the process !!!'

        elif proc_tag > 0:
            cmdrs = self._execute_query(cmdarg, proc_tag)
            result.data = cmdrs
            if 0 != cmdrs.errcode:
                result.errcode = cmdrs.errcode
                result.text = '\n'.join(cmdrs.stderr)
        else:
            pass

        return result

    def text(self, title: str, data: bytes = b''):

        ask_chunk = header_text(action_kind.ask, title, data)
        self._send(ask_chunk.pack())

        is_there_a_chunk = self._wait_until(len,
                                            0.1,
                                            _WAIT_TIMEOUT_,
                                            self.sock.chunk_list)
        if is_there_a_chunk:
            done_chunk: header_text = self.sock.chunk_list.pop(0)

            result = rcresult()
            result.data = done_chunk.payload_chunk
            result.text = title

            return result
        else:
            return error_wait_timeout_streaming

    def get_computer_info(self):

        result: rcresult = self.text('computer_info')
        text = str(result.data, encoding='utf-8')
        data: computer_info = config().toCLASS(text)
        return data

    def mkdir(self, path: str):
        result: rcresult = self.text('inncmd_mkdir', path.encode())
        text = str(result.data, encoding='utf-8')
        data: inncmd_mkdir = config().toCLASS(text)
        return data


if __name__ == '__main__':

    prefix = '[%(asctime)s][%(levelname)s]' + \
             '[%(filename)s!%(funcName)s:%(lineno)d] %(message)s'
    format = logging.Formatter(prefix, datefmt='%Y%m%d %H:%M:%S')
    screen = logging.StreamHandler()
    screen.setFormatter(format)
    logger = logging.getLogger()
    logger.addHandler(screen)
    logger.setLevel(logging.INFO)

    _HOST_ = 'localhost'
    _PORT_ = 12345

    if len(sys.argv) > 1:

        if sys.argv[1] == 'server':
            rcsrv = rcserver(_HOST_, _PORT_)
            rcsrv.start()

        elif sys.argv[1] == 'client':
            rcclt = rcclient()

            # if rcclt.connect('localhost', 10013):
            if rcclt.connect('localhost', 10013):
                # result = rcclt.upload('../MyApp.exe', '.')
                # result = rcclt.upload('../calc.exe', '.')
                # result = rcclt.upload('../VirtualBox.exe', '.')
                # result = rcclt.list('README.md')
                # result = rcclt.list('.')

                # result = rcclt.execute('ifconfig')
                # result = rcclt.execute('devcon64', 'rescan')
                # result = rcclt.upload('../UsbTreeView.exe', '.')
                result = rcclt.execute('pwd')

                # # # # # # # # # # #
                # Windows commands  #
                # # # # # # # # # # #
                # result = rcclt.execute('ipconfig')
                # result = rcclt.execute('systeminfo')

                if 0 == result.errcode:
                    logging.info("errcode={}".format(result.errcode))
                    logging.info("data={}".format(result.data))
                else:
                    logging.error("errcode={}".format(result.errcode))
                    logging.error("text={}".format(result.text))
            else:
                logging.error("Failed to connect to server !!!")

