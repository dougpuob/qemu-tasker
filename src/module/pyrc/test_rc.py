import os
import json
import base64
import shutil
import filecmp
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
from rc import header_text
from rc import config
from rc import computer_info
from rc import inncmd_mkdir
from rc import action_kind
from rc import action_name
from rc import execute_subcmd


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
    pattern_KB: list = [1*_KB_, 5*_KB_, 10*_KB_]
    pattern_MB: list = [1*_MB_, 5*_MB_, 10*_MB_]
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
        with open(filepath, 'wb') as f:
            f.write(os.urandom(item))
            f.flush()
            f.close()


def thread_routine(server: rcserver):
    if server:
        server.start()


def setup_module(module):
    server = rcserver(_HOST_, _PORT_, debug_enabled=True)
    new_thread = threading.Thread(target=thread_routine,
                                  args=(server,))
    new_thread.daemon = True
    new_thread.start()

    prepare_pattern_files()


def teardown_module(module):

    if os.path.exists(_TESTDIR_):
        shutil.rmtree(_TESTDIR_)

    if os.path.exists(_TEMPDIR_ULOAD_):
        shutil.rmtree(_TEMPDIR_ULOAD_)

    if os.path.exists(_TEMPDIR_DLOAD_):
        shutil.rmtree(_TEMPDIR_DLOAD_)


class TestPyRc(unittest.TestCase):

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

        hdr = header_upload(action_kind.ask,
                            _FILENAME_,
                            _DATA_SIZE_,
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
        _PROGRAM_ = 'ipconfig我'.encode('utf-8')
        _ARGUMENT_ = '/all我'.encode('utf-8')
        _WORKDIR_ = ''.encode('utf-8')
        _ISBASE64_ = False
        _DATA_ = b''

        hdr = header_execute(action_kind.ask,
                             execute_subcmd.start,
                             _PROGRAM_,
                             _ARGUMENT_,
                             _WORKDIR_,
                             _ISBASE64_)

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
        self.assertEqual(_PROGRAM_, output_hdr.exec.program)
        self.assertEqual(_ARGUMENT_, output_hdr.exec.argument)
        self.assertEqual(_ISBASE64_, output_hdr.exec.isbase64)
        self.assertEqual(_WORKDIR_, output_hdr.exec.workdir)

    def test_header_text_ask(self):
        _DATA_ = computer_info().toTEXT().encode()

        hdr = header_text(action_kind.ask, 'computer_info', _DATA_)

        hdr.chunk_size = len(_DATA_)
        hdr.chunk_count = 1
        hdr.chunk_index = 0

        packed_data = hdr.pack()
        self.assertIsNotNone(packed_data)

        output_hdr = hdr.unpack(packed_data)
        self.assertTrue(isinstance(output_hdr, header_text))

        self.assertEqual(action_kind.ask.value, output_hdr.action_kind)
        self.assertEqual(action_name.text.value, output_hdr.action_name)

        self.assertEqual(output_hdr.chunk_size, len(_DATA_))
        self.assertEqual(output_hdr.chunk_count, 1)
        self.assertEqual(output_hdr.chunk_index, 0)

        self.assertEqual(_DATA_, output_hdr.payload_chunk)

        text = str(output_hdr.payload_chunk, encoding='utf-8')
        data: computer_info = config().toCLASS(text)
        self.assertEqual(data.osname, data.osname)
        self.assertEqual(data.homedir, data.homedir)

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

    def test_connect_then_list_not_existing(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.list('noexistingfolder')
        self.assertEqual(0, result.errcode)

    def test_connect_then_list_cwd(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: rcresult = client.list(_TESTDIR_)
        self.assertEqual(0, result.errcode)

    def test_connect_then_download_usbtreeview_bin(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        filename = 'PATTERN_764444_UsbTreeView.bin'
        srcfilepath = os.path.join(_TESTDIR_, filename)
        UsbTreeViewExe = os.urandom(764444)
        f = open(srcfilepath, 'wb')
        if f:
            f.write(UsbTreeViewExe)
            f.flush()
            f.close()

        result: rcresult = client.download(srcfilepath, _TEMPDIR_DLOAD_)
        self.assertEqual(0, result.errcode)

        dstfilepath = os.path.join(_TEMPDIR_DLOAD_, filename)
        is_there = os.path.exists(dstfilepath)
        self.assertEqual(True, is_there)

        cmp_matched = filecmp.cmp(srcfilepath, dstfilepath)
        self.assertEqual(True, cmp_matched)

    def test_connect_then_download_not_existing_file(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        fileloc = os.path.abspath('aaabbbcccdddeee.bin')
        self.assertEqual(False, os.path.exists(fileloc))

        result: rcresult = client.download(fileloc, '.')
        self.assertEqual(3, result.errcode)

        self.assertEqual(False, os.path.exists(fileloc))

    def test_connect_then_download_all_testdata(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        for file in pattern_name_list:
            filename = os.path.basename(file)

            fileloc_src = os.path.abspath(os.path.join(_TESTDIR_, filename))
            fileloc_dst = os.path.abspath(os.path.join(_TEMPDIR_DLOAD_,
                                                       filename))

            self.assertEqual(os.path.exists(fileloc_src), True)
            self.assertEqual(os.path.exists(fileloc_dst), False)
            result: rcresult = client.download(file, _TEMPDIR_DLOAD_)
            self.assertEqual(0, result.errcode)
            self.assertEqual(os.path.exists(fileloc_dst), True)

            filesize_src = os.path.getsize(fileloc_src)
            filesize_dst = os.path.getsize(fileloc_dst)
            msg = 'filesize_src={} filesize_dst={}'.format(filesize_src,
                                                           filesize_dst)
            self.assertEqual(filesize_src, filesize_dst, msg)

            self.assertEqual(os.path.exists(fileloc_src), True)
            self.assertEqual(os.path.exists(fileloc_dst), True)

            cmp_matched = True
            file_src = open(fileloc_src, 'rb')
            file_dst = open(fileloc_dst, 'rb')
            if file_src and file_dst:
                self.assertEqual(True, filesize_src == filesize_dst)

                data_src = file_src.read(filesize_src)
                data_dst = file_dst.read(filesize_dst)
                self.assertEqual(True, len(data_src) > 0)
                self.assertEqual(True, len(data_dst) > 0)

                index = 0
                while index < filesize_src:
                    if cmp_matched:
                        cmp_matched = (data_dst[index] == data_src[index])
                    index += 1

                file_src.close()
                file_dst.close()

            logfmt = 'filesize_src={} filesize_dst={} cmp_matched={}'
            msg = logfmt.format(filesize_src,
                                filesize_dst,
                                cmp_matched)
            self.assertEqual(True, cmp_matched, msg)

    def test_connect_then_upload_usbtreeview(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        filepath = os.path.join(_TESTDIR_, 'PATTERN_764448_UsbTreeView.bin')
        UsbTreeViewExe = os.urandom(764448)
        f = open(filepath, 'wb')
        if f:
            f.write(UsbTreeViewExe)
            f.flush()
            f.close()

        # Upload files
        result: rcresult = client.upload(filepath, _TEMPDIR_ULOAD_)
        self.assertEqual(0, result.errcode)

        dstfilepath = os.path.join(_TEMPDIR_ULOAD_,
                                   'PATTERN_764448_UsbTreeView.bin')
        if os.path.exists(dstfilepath):
            os.unlink(dstfilepath)
            if os.path.exists(dstfilepath):
                pass
            else:
                pass

    def test_connect_then_upload_all_testdata(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        # Check not existing
        index = 0
        for file in pattern_name_list:
            filename = os.path.basename(file)
            fileloc_dst = os.path.join(_TEMPDIR_ULOAD_, filename)
            mesg = 'index={} filename={} fileloc={}'.format(index,
                                                            filename,
                                                            fileloc_dst)
            existing = os.path.exists(fileloc_dst)
            mesg = '{} NotThere={}'.format(mesg, not existing)
            self.assertFalse(os.path.exists(fileloc_dst), mesg)
            index += 1

        # Upload files
        index = 0
        for file in pattern_name_list:
            filename = os.path.basename(file)
            fileloc_dst = os.path.join(_TEMPDIR_ULOAD_, filename)
            mesg = 'index={} filename={} fileloc={}'.format(index,
                                                            filename,
                                                            fileloc_dst)
            result: rcresult = client.upload(file, _TEMPDIR_ULOAD_)
            self.assertEqual(0, result.errcode, mesg)
            index += 1

        # Check should exist
        index = 0
        for file in pattern_name_list:
            filename = os.path.basename(file)
            fileloc_src = os.path.join(_TESTDIR_, filename)
            fileloc_dst = os.path.join(_TEMPDIR_ULOAD_, filename)
            cmp_matched = filecmp.cmp(fileloc_src, fileloc_dst)
            mesg = 'index={} filename={} fileloc={}'.format(index,
                                                            filename,
                                                            fileloc_dst)
            mesg = '{} where={} matched={}'.format(mesg,
                                                   os.path.exists(fileloc_dst),
                                                   cmp_matched)
            self.assertTrue(os.path.exists(fileloc_dst), mesg)
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

    def test_connect_then_execute_ifconfig_base64(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        if platform.system() == 'Windows':
            base64_arg = base64.b64encode('/all'.encode('utf-8')).decode()
            result: rcresult = client.execute('ipconfig', base64_arg,
                                              isbase64=True)
            self.assertEqual(0, result.errcode)
        elif platform.system() == 'Darwin':
            base64_arg = base64.b64encode(''.encode('utf-8')).decode()
            result: rcresult = client.execute('ifconfig', base64_arg,
                                              isbase64=True)
            self.assertEqual(0, result.errcode)
        elif platform.system() == 'Linux':
            base64_arg = base64.b64encode('a'.encode('utf-8')).decode()
            result: rcresult = client.execute('ip', base64_arg,
                                              isbase64=True)
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
            self.assertEqual('', result.text)
            self.assertEqual(result.errcode, result.data.errcode)
        else:
            result: rcresult = client.execute('uname')
            self.assertEqual(0, result.errcode)

    def test_connect_then_execute_systeminfo_with_workdir(self):
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
        self.assertNotEqual(0, result.errcode)

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
        self.assertNotEqual(0, result.errcode)

    def test_connect_then_text_computer_info(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        osname = platform.system().lower()
        data1 = computer_info(osname, os.path.expanduser('~'))
        result: rcresult = client.text('computer_info')
        self.assertEqual(result.errcode, 0)
        self.assertEqual(result.text, 'computer_info')
        text = str(result.data, encoding='utf-8')
        data2: computer_info = config().toCLASS(text)
        self.assertEqual(data1.osname, data2.osname)
        self.assertEqual(data1.homedir, data2.homedir)

    def test_connect_then_get_computer_info(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        result: computer_info = client.get_computer_info()
        self.assertEqual('' != result.osname, True)
        self.assertEqual('' != result.homedir, True)

    def test_connect_then_mkdir_1(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        path = os.path.join(_TESTDIR_, 'inncmd_mkdir_1')
        self.assertEqual(os.path.exists(path), False)
        result: inncmd_mkdir = client.mkdir(path)
        self.assertEqual(result.path, path)
        self.assertEqual(result.result, True)
        self.assertEqual(os.path.exists(path), True)

        if os.path.exists(path):
            os.rmdir(path)

    def test_connect_then_mkdir_2(self):
        client = rcclient()
        self.assertEqual(client.connect(_HOST_, _PORT_), True)
        self.assertEqual(client.is_connected(), True)

        path = os.path.join(_TESTDIR_, 'inncmd_mkdir_2', 'AA')
        self.assertEqual(os.path.exists(path), False)
        result: inncmd_mkdir = client.mkdir(path)
        self.assertEqual(result.path, path)
        self.assertEqual(result.result, True)
        self.assertEqual(os.path.exists(path), True)

        if os.path.exists(path):
            os.rmdir(path)


if __name__ == '__main__':
    unittest.main()
