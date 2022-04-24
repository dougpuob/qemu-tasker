# -*- coding: utf-8 -*-
import argparse


class cmdargs():
    def __init__(self):
        #
        # Program arugments
        #
        parent_parser = argparse.ArgumentParser(add_help=False)
        self.parser = argparse.ArgumentParser(add_help=True)

        # create sub-parser
        subparsers = self.parser.add_subparsers(dest="command")
        self.parser.add_argument('-H', '--host', type=str, default="localhost")
        self.parser.add_argument('-P', '--port', type=int, default=12801)
        self.parser.add_argument('-J', '--jsonreport', action='store_true', default=False)
        self.parser.add_argument('-V', '--version', action='version', version='%(prog)s 0.1')
        self.parser.add_argument('-L', '--logdir', type=str)
        self.parser.add_argument('-S', '--setting', type=str, default="setting.json")

        # subcommand server
        parser_server = subparsers.add_parser('server', parents = [parent_parser], help='start a server daemon')
        parser_server.add_argument('-L', '--longlife', type=int, default=30)

        # subcommand info
        parser_info = subparsers.add_parser('info', parents = [parent_parser], help='get server system information')

        # subcommand start
        parser_start = subparsers.add_parser('start', parents = [parent_parser], help='launch a QEMU achine instance')
        parser_start.add_argument('-C', '--config', type=str, required=True)
        parser_start.add_argument('-T', '--test',  action='store_true')

        # subcommand kill
        parser_kill = subparsers.add_parser('kill', parents = [parent_parser], help='kill the specific QEMU machine instance')
        parser_kill.add_argument('-T', '--taskid', type=int)
        parser_kill.add_argument('-A', '--killall', action='store_true')

        # # subcommand exec
        # parser_exec = subparsers.add_parser('exec', parents = [parent_parser], help='execute a specific command at guest operating system')
        # parser_exec.add_argument('-T', '--taskid', type=int, required=True)
        # parser_exec.add_argument('-P', '--program', required=True)
        # parser_exec.add_argument('-A', '--argument')
        # parser_exec.add_argument('-B64', '--base64', action='store_true')

        # subcommand qmp
        parser_qmp = subparsers.add_parser('qmp', parents = [parent_parser], help='execute a specific QMP command')
        parser_qmp.add_argument('-T', '--taskid', type=int, required=True)
        parser_qmp.add_argument('-E', '--execute', required=True)
        parser_qmp.add_argument('-J', '--argsjson')
        parser_qmp.add_argument('-B64', '--base64', action='store_true')

        # subcommand puppet
        parser_puppet = subparsers.add_parser('puppet', parents = [parent_parser], help='start a puppet daemon')

        # subcommand execute
        parser_execute = subparsers.add_parser('execute', parents = [parent_parser], help='execute a specific command at guest operating system')
        parser_execute.add_argument('-T', '--taskid', type=int, required=True)
        parser_execute.add_argument('-P', '--program', required=True)
        parser_execute.add_argument('-A', '--argument')
        parser_execute.add_argument('-W', '--workdir', type=str, default=".")
        parser_execute.add_argument('-B64', '--base64', action='store_true')

        # subcommand `list`
        parser_list = subparsers.add_parser('list', parents = [parent_parser], help='list files from local to guest')
        parser_list.add_argument('-T', '--taskid', type=int, required=True)
        parser_list.add_argument('-D', '--dstdir', type=str)

        # subcommand `download`
        parser_download = subparsers.add_parser('download', parents = [parent_parser], help='download files from guest to local')
        parser_download.add_argument('-T', '--taskid', type=int, required=True)
        parser_download.add_argument('-F', '--files', required=True, nargs="+")
        parser_download.add_argument('-D', '--dstdir', type=str)

        # subcommand `upload`
        parser_upload = subparsers.add_parser('upload', parents = [parent_parser], help='upload files from local to guest')
        parser_upload.add_argument('-T', '--taskid', type=int, required=True)
        parser_upload.add_argument('-F', '--files', required=True, nargs="+")
        parser_upload.add_argument('-D', '--dstdir', type=str)

        # subcommand `push`
        parser_push = subparsers.add_parser('push', parents = [parent_parser], help='update files from local to guest')
        parser_push.add_argument('-T', '--taskid', type=int, required=True)

        # subcommand status
        parser_status = subparsers.add_parser('status', parents = [parent_parser], help='query a specific QEMU status')
        parser_status.add_argument('-T', '--taskid', type=int, required=True)



    def print_help(self):
        args = self.parser.print_help()
        return args


    def get_parsed_args(self):
        args = self.parser.parse_args()
        return args
