import os
import json
import base64
import shutil
import logging
import platform
import unittest
import threading

from rc import rcresult
from rc import rcserver
from rc import rcclient
from rc import header_echo
from rc import header_upload
from rc import header_download
from rc import header_list
from rc import header_execute
from rc import action_kind
from rc import action_name

_HOST_ = 'localhost'
_PORT_ = 12345
_TESTDIR_ = 'testdata'
_TEMPDIR_ULOAD_ = 'tempdir_upload'
_TEMPDIR_DLOAD_ = 'tempdir_download'
pattern_name_list = list()


def prepare_pattern_files():
    _KB_ = 1024
    _MB_ = 1024*1024

    # Generate temporary binary files
    pattern_B: list = [32, 64, 128, 256, 512]
    pattern_KB: list = [1*_KB_, 5*_KB_]
    pattern_MB: list = [1*_MB_, 5*_MB_]
    pattern_all = pattern_B + pattern_KB + pattern_MB

    if os.path.exists(_TESTDIR_):
        shutil.rmtree(_TESTDIR_)

    if os.path.exists(_TEMPDIR_ULOAD_):
        shutil.rmtree(_TEMPDIR_ULOAD_)

    if os.path.exists(_TEMPDIR_DLOAD_):
        shutil.rmtree(_TEMPDIR_DLOAD_)

    os.mkdir(_TESTDIR_)
    os.mkdir(_TEMPDIR_ULOAD_)
    os.mkdir(_TEMPDIR_DLOAD_)

    for item in pattern_all:
        filename = 'PATTERN_{}.bin'.format(item)
        filepath = os.path.join(_TESTDIR_, filename)
        pattern_name_list.append(filepath)
        with open(filepath, 'wb') as fout:
            fout.write(os.urandom(item))


def thread_routine(server: rcserver):
    if server:
        server.start()


def setup_module(module):
    prepare_pattern_files()

    server = rcserver(_HOST_, _PORT_, debug_enabled=True)
    new_thread = threading.Thread(target=thread_routine,
                                  args=(server,))
    new_thread.setDaemon(True)
    new_thread.start()


def teardown_module(module):

    if os.path.exists(_TESTDIR_):
        shutil.rmtree(_TESTDIR_)

    if os.path.exists(_TEMPDIR_ULOAD_):
        shutil.rmtree(_TEMPDIR_ULOAD_)

    if os.path.exists(_TEMPDIR_DLOAD_):
        shutil.rmtree(_TEMPDIR_DLOAD_)


class Test_service(unittest.TestCase):

    def __init__(self, methodName: str = ...):
        super().__init__(methodName)

    def thread_routine(self, server: rcserver):
        if server:
            server.start()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_header_echo_no_data(self):

        hdr = header_echo(action_kind.ask)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = 0
        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_echo))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.echo.value, output_hdr.action_name)

    def test_header_upload_no_data(self):
        _DATA_SIZE_ = 10
        _FILENAME_ = 'File.bin'
        _DIRPATH_ = '.'

        hdr = header_upload(action_kind.ask, _FILENAME_, _DATA_SIZE_,
                            _DIRPATH_)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = _DATA_SIZE_
        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_upload))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.upload.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(_DATA_SIZE_, output_hdr.chunk_size)

        self.assertEqual(_FILENAME_, output_hdr.filename)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(b'', output_hdr.data)

    def test_header_upload_data_10B(self):
        _DATA_SIZE_ = 10
        _FILENAME_ = 'File10B.bin'
        _DIRPATH_ = '.'
        _DATA_ = os.urandom(_DATA_SIZE_)
        hdr = header_upload(action_kind.ask, _FILENAME_, _DATA_SIZE_,
                            _DIRPATH_, _DATA_)
        hdr.chunk_count = 1
        hdr.chunk_index = 0
        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_upload))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.upload.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(_DATA_SIZE_, output_hdr.chunk_size)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_FILENAME_, output_hdr.filename)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(_DATA_, output_hdr.data)

    def test_header_upload_data_1KB(self):
        _DATA_SIZE_ = 1024
        _FILENAME_ = 'File1KB.bin'
        _DIRPATH_ = '.'
        _DATA_ = os.urandom(_DATA_SIZE_)
        hdr = header_upload(action_kind.ask, _FILENAME_, _DATA_SIZE_,
                            _DIRPATH_, _DATA_)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = _DATA_SIZE_

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_upload))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.upload.value, output_hdr.action_name)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_FILENAME_, output_hdr.filename)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(_DATA_, output_hdr.data)

    def test_header_upload_data_1MB(self):
        _DATA_SIZE_ = 1024*1024
        _FILENAME_ = 'File1MB.bin'
        _DIRPATH_ = '.'
        _DATA_ = os.urandom(_DATA_SIZE_)
        hdr = header_upload(action_kind.ask, _FILENAME_, _DATA_SIZE_,
                            _DIRPATH_, _DATA_)
        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = _DATA_SIZE_

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_upload))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.upload.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(_DATA_SIZE_, output_hdr.chunk_size)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_FILENAME_, output_hdr.filename)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(_DATA_, output_hdr.data)

    def test_header_download_data_1MB(self):
        _DATA_SIZE_ = 1024*1024
        _FILENAME_ = 'File1MB.bin'
        _DATA_ = os.urandom(_DATA_SIZE_)
        hdr = header_download(action_kind.ask, _FILENAME_, _DATA_SIZE_,
                              _DATA_)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = _DATA_SIZE_

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_download))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.download.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(_DATA_SIZE_, output_hdr.chunk_size)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_FILENAME_, output_hdr.filepath)
        self.assertEqual(_DATA_, output_hdr.data)

    def test_header_list_ask(self):
        _DIRPATH_ = '.'
        _DATA_ = b''
        hdr = header_list(action_kind.ask, _DIRPATH_, _DATA_)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = len(_DATA_)

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_list))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.list.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(len(_DATA_), output_hdr.chunk_size)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(_DATA_, output_hdr.data)

    def test_header_list_data_no_file(self):
        _MYLIST_ = []

        _DIRPATH_ = '.'
        _DATA_ = json.dumps(_MYLIST_).encode()

        hdr = header_list(action_kind.data, _DIRPATH_, _DATA_)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = len(_DATA_)

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_list))

        self.assertEqual(action_kind.data.value, output_hdr.action_kind)
        self.assertEqual(action_name.list.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(len(_DATA_), output_hdr.chunk_size)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(_DATA_, output_hdr.data)
        self.assertEqual(_MYLIST_, json.loads(output_hdr.data))

    def test_header_list_data_three_files(self):
        __MYLIST__ = ['File1.bin', 'File2.bin', 'File3.bin']

        _DIRPATH_ = '.'
        _DATA_ = json.dumps(__MYLIST__).encode()

        hdr = header_list(action_kind.data, _DIRPATH_, _DATA_)

        hdr.chunk_count = 1
        hdr.chunk_index = 0
        hdr.chunk_size = len(_DATA_)

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_list))

        self.assertEqual(action_kind.data.value, output_hdr.action_kind)
        self.assertEqual(action_name.list.value, output_hdr.action_name)

        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)
        self.assertEqual(len(_DATA_), output_hdr.chunk_size)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_DIRPATH_, output_hdr.dstdirpath)
        self.assertEqual(_DATA_, output_hdr.data)
        self.assertEqual(__MYLIST__, json.loads(output_hdr.data))

    def test_header_execute_ask(self):
        _PROGRAM_ = 'ipconfig'
        _ARGUMENT_ = '/all我'
        _ARGUMENT_UTF8_ = _ARGUMENT_.encode('utf-8')
        _ARGUMENT_B64_ = base64.b64encode(_ARGUMENT_UTF8_)
        _WORKDIR_ = ''
        _DATA_ = b''

        hdr = header_execute(action_kind.ask, _PROGRAM_, _ARGUMENT_, _WORKDIR_)

        hdr.chunk_size = len(_DATA_)
        hdr.chunk_count = 1
        hdr.chunk_index = 0

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_execute))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.execute.value, output_hdr.action_name)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(1, output_hdr.chunk_count)
        self.assertEqual(0, output_hdr.chunk_index)

        self.assertEqual(len(_DATA_), output_hdr.chunk_size)
        self.assertEqual(_PROGRAM_, output_hdr.program)
        self.assertEqual(_ARGUMENT_, output_hdr.argument)
        self.assertEqual(_ARGUMENT_UTF8_, output_hdr.argument_utf8)
        self.assertEqual(_ARGUMENT_B64_, output_hdr.argument_base64)
        self.assertEqual(_WORKDIR_, output_hdr.workdir)

    def test_connect(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

    def test_connect_then_list(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.list(_TESTDIR_)
        logging.info("result.data={}".format(result.data))
        self.assertEqual(0, result.errcode)

    def test_connect_then_list_cwd(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.list(_TESTDIR_)
        self.assertEqual(0, result.errcode)
        self.assertEqual(len(pattern_name_list), len(result.data))

    def test_connect_then_download_all_testdata(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        for file in pattern_name_list:

            filename = os.path.basename(file)
            fileloc = os.path.join(_TEMPDIR_DLOAD_, filename)

            self.assertFalse(os.path.exists(fileloc))

            result: rcresult = client.download(file, _TEMPDIR_DLOAD_)
            self.assertEqual(0, result.errcode)

            self.assertTrue(os.path.exists(fileloc))

    def test_connect_then_upload_all_testdata(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        # Check not existing
        index = 0
        for file in pattern_name_list:
            filename = os.path.basename(file)
            fileloc = os.path.join(_TEMPDIR_ULOAD_, filename)
            mesg = 'index={} filename={} fileloc={}'.format(index,
                                                            filename,
                                                            fileloc)
            mesg = '{} NotThere={}'.format(mesg, not os.path.exists(fileloc))
            self.assertFalse(os.path.exists(fileloc), mesg)
            index += 1

        # Upload files
        index = 0
        for file in pattern_name_list:
            filename = os.path.basename(file)
            fileloc = os.path.join(_TEMPDIR_ULOAD_, filename)
            mesg = 'index={} filename={} fileloc={}'.format(index,
                                                            filename,
                                                            fileloc)
            result: rcresult = client.upload(file, _TEMPDIR_ULOAD_)
            self.assertEqual(0, result.errcode, mesg)
            index += 1

        # Check should exist
        index = 0
        for file in pattern_name_list:
            filename = os.path.basename(file)
            fileloc = os.path.join(_TEMPDIR_ULOAD_, filename)
            mesg = 'index={} filename={} fileloc={}'.format(index,
                                                            filename,
                                                            fileloc)
            mesg = '{} There={}'.format(mesg,
                                        os.path.exists(fileloc))
            self.assertTrue(os.path.exists(fileloc), mesg)
            index += 1

    def test_connect_then_execute_ifconfig(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        if platform.system() == 'Windows':
            result: rcresult = client.execute('ipconfig', '/all')
            self.assertEqual(0, result.errcode)
        elif platform.system() == 'Darwin':
            result: rcresult = client.execute('ifconfig')
            self.assertEqual(0, result.errcode)
        elif platform.system() == 'Linux':
            result: rcresult = client.execute('ip', 'a')
            self.assertEqual(0, result.errcode)

    def test_connect_then_execute_dir(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        if platform.system() == 'Windows':
            result: rcresult = client.execute('dir')
            self.assertEqual(0, result.errcode)
        else:
            result: rcresult = client.execute('ls')
            self.assertEqual(0, result.errcode)

    def test_connect_then_execute_systeminfo(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        if platform.system() == 'Windows':
            result: rcresult = client.execute('systeminfo')
            self.assertEqual(0, result.errcode)
        else:
            result: rcresult = client.execute('uname')
            self.assertEqual(0, result.errcode)

    def test_connect_then_execute_systeminfo_(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        if platform.system() == 'Windows':
            result: rcresult = client.execute('systeminfo', '', '.')
            self.assertEqual(0, result.errcode)
        else:
            result: rcresult = client.execute('uname', '', '.')
            self.assertEqual(0, result.errcode)

    def test_connect_then_execute_unknown(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.execute('unknown')
        self.assertEqual(result.data.errcode, result.errcode)
        self.assertIsNot(0, result.errcode)

    def test_connect_then_execute_mkdir(self):
        if os.path.exists('mkdir'):
            os.removedirs('mkdir')

        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        self.assertEqual(os.path.exists('mkdir'), False)
        result: rcresult = client.execute('mkdir', 'mkdir')
        self.assertEqual(result.data.errcode, result.errcode)
        self.assertEqual(0, result.errcode)
        self.assertEqual(os.path.exists('mkdir'), True)

        os.removedirs('mkdir')
        self.assertEqual(os.path.exists('mkdir'), False)

    def test_connect_then_execute_pwsh_cmd(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.execute('(Get-Location).Path')
        self.assertEqual(result.data.errcode, result.errcode)
        self.assertEqual(2, result.errcode)

    def test_connect_then_execute_pwd(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.execute('pwd')
        self.assertEqual(result.data.errcode, result.errcode)
        self.assertEqual(0, result.errcode)

if __name__ == '__main__':
    unittest.main()
