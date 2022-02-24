# -*- coding: utf-8 -*-
import argparse

class cmdargs():
    def __init__(self) -> None:
        #
        # Program arugments
        #
        parent_parser = argparse.ArgumentParser(add_help=False)
        self.parser = argparse.ArgumentParser(add_help=True) 

        # create sub-parser
        subparsers = self.parser.add_subparsers(dest="command")
        self.parser.add_argument('-H', '--host', type=str, default="localhost")
        self.parser.add_argument('-P', '--port', type=int, default=12801)
        self.parser.add_argument('-V', '--verbose', action='store_true')

        # subcommand start                                                                  
        parser_server = subparsers.add_parser('server', parents = [parent_parser], help='start a server daemon')

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
        parser_exec.add_argument('-A', '--arguments', default="")

        # subcommand qmp
        parser_exec = subparsers.add_parser('qmp', parents = [parent_parser], help='execute a specific QMP command')
        parser_exec.add_argument('-T', '--taskid', type=int, required=True)
        parser_exec.add_argument('-E', '--execute', required=True)
        parser_exec.add_argument('-A', '--argsjson')

        # subcommand file
        parser_file = subparsers.add_parser('file', parents = [parent_parser], help='transfer files between client and guest, or server and guest')
        parser_file.add_argument('-T', '--taskid', type=int, required=True)
        parser_file.add_argument('-K', '--kind', type=str, required=True, choices=['c2g_upload', 
                                                                                   'c2g_download', 
                                                                                   's2g_upload', 
                                                                                   's2g_download'])
        parser_file.add_argument('-F', '--filepath', type=str, required=True)
        parser_file.add_argument('-S', '--savepath', type=str, required=True)
        parser_file.add_argument('-N', '--newdir', type=str)
        parser_file.add_argument('-C', '--config', type=str)
        parser_file.add_argument('-P', '--port', type=int)

    def get_parsed_args(self):
        args = self.parser.parse_args()
        return args
