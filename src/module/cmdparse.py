# -*- coding: utf-8 -*-
import argparse
import json

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
        self.parser.add_argument('-V', '--verbose', action='store_true')

        # subcommand start
        parser_server = subparsers.add_parser('server', parents = [parent_parser], help='start a server daemon')
        parser_server.add_argument('-L', '--longlife', type=int, default=30)
        parser_server.add_argument('-F', '--filepool', type=str, default="./filepool")        

        # subcommand start
        parser_start = subparsers.add_parser('start', parents = [parent_parser], help='launch a QEMU achine instance')
        parser_start.add_argument('-C', '--config', required=True)
        parser_start.add_argument('-T', '--test',  action='store_true')

        # subcommand kill
        parser_kill = subparsers.add_parser('kill', parents = [parent_parser], help='kill the specific QEMU machine instance')
        parser_kill.add_argument('-T', '--taskid', type=int)
        parser_kill.add_argument('-A', '--killall', action='store_true')

        # subcommand exec
        parser_exec = subparsers.add_parser('exec', parents = [parent_parser], help='execute a specific command at guest operating system')
        parser_exec.add_argument('-T', '--taskid', type=int, required=True)
        parser_exec.add_argument('-P', '--program', required=True)
        parser_exec.add_argument('-A', '--argument')

        # subcommand qmp
        parser_exec = subparsers.add_parser('qmp', parents = [parent_parser], help='execute a specific QMP command')
        parser_exec.add_argument('-T', '--taskid', type=int, required=True)
        parser_exec.add_argument('-E', '--execute', required=True)
        parser_exec.add_argument('-J', '--argsjson')
        parser_exec.add_argument('-F', '--argsfile')

        # subcommand file
        parser_file = subparsers.add_parser('file', parents = [parent_parser], help='transfer files between local and guest, or server and guest')
        parser_file.add_argument('-T', '--taskid', type=int, required=True)
        parser_file.add_argument('-SF', '--sendfrom', type=str, required=True, choices=['local','server','guest'])
        parser_file.add_argument('-ST', '--sendto', type=str, required=True, choices=['local','server','guest'])
        parser_file.add_argument('-PF', '--pathfrom', type=str, required=True)
        parser_file.add_argument('-PT', '--pathto', type=str, required=True)
        parser_file.add_argument('-C', '--config', type=str)
        parser_file.add_argument('-P', '--port', type=int)
        
        # subcommand `download`
        parser_download = subparsers.add_parser('download', parents = [parent_parser], help='download files from guest to local')
        parser_download.add_argument('-T', '--taskid', type=int, required=True)
        parser_download.add_argument('-F', '--files', required=True, nargs="+")
        parser_download.add_argument('-S', '--saveto', type=str, required=True)

        # subcommand `upload`
        parser_upload = subparsers.add_parser('upload', parents = [parent_parser], help='upload files from local to guest')
        parser_upload.add_argument('-T', '--taskid', type=int, required=True)
        parser_upload.add_argument('-F', '--files', required=True, nargs="+")
        parser_upload.add_argument('-S', '--saveto', type=str, required=True)

        # subcommand status
        parser_exec = subparsers.add_parser('status', parents = [parent_parser], help='query a specific QEMU status')
        parser_exec.add_argument('-T', '--taskid', type=int, required=True)

    def print_help(self):
        args = self.parser.print_help()
        return args

    def get_parsed_args(self):
        args = self.parser.parse_args()
        return args
