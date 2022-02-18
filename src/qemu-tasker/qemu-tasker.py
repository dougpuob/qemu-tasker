# -*- coding: utf-8 -*-
import argparse
import pathlib
import logging
import json

from module import config
from module.server import server
from module.client import client


parent_parser = argparse.ArgumentParser(add_help=False)
parser = argparse.ArgumentParser(add_help=True) 

# create sub-parser
subparsers = parser.add_subparsers(dest="command")

# subcommand start                                                                  
parser_start = subparsers.add_parser('server', parents = [parent_parser], help='start a server daemon')

# subcommand start
parser_start = subparsers.add_parser('start', parents = [parent_parser], help='launch a QEMU achine instance')
parser_start.add_argument('-C', '--config', required=True)
parser_start.add_argument('-T', '--test',  action='store_true')

# subcommand kill
parser_kill = subparsers.add_parser('kill', parents = [parent_parser], help='kill the specific QEMU machine instance')
parser_kill.add_argument('-T', '--taskid', type=int)
parser_kill.add_argument('-A', '--killall',  action='store_true')

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

args = parser.parse_args()
print("{}● args={}".format("", args))

logging.basicConfig(filename='default.log', 
                    level=logging.INFO,
                    format="[%(asctime)s][%(levelname)s] %(message)s",
                    datefmt='%Y-%m-%d-%H:%M:%S')

logging.info('--------------------------------------------------------------------------------')
logging.info(args)

srvcfg_path = pathlib.Path.joinpath(pathlib.Path(__file__).parent.absolute(), 'config/server-config.json')
srvcfg_json = json.load(open(srvcfg_path))

socket_addr = config.socket_address(srvcfg_json['socket_address']['addr'], 
                                    srvcfg_json['socket_address']['port'])

if 'server' == args.command:
    server(socket_addr).start()

elif 'start' == args.command:
    assert args.config, "Please specific a config file !!!"
    client_cfg = json.load(open(args.config))
    start_cfg = config.start_config(client_cfg)
    client(socket_addr).send_start(start_cfg)

elif 'exec' == args.command:
    exec_args = config.exec_arguments(args.program, args.arguments.split(' '))
    exec_cmd = config.exec_command(args.taskid, exec_args)    
    exec_cfg = config.exec_config(exec_cmd.toJSON())
    client(socket_addr).send_exec(exec_cfg)

elif 'kill' == args.command:
    kill_cmd = config.kill_command(args.taskid, args.killall)
    kill_cfg = config.kill_config(kill_cmd.toJSON())
    client(socket_addr).send_kill(kill_cfg)

elif 'qmp' == args.command:
    qmp_cmd = config.qmp_command(args.taskid, args.execute, args.argsjson)
    qmp_cfg = config.qmp_config(qmp_cmd.toJSON())
    client(socket_addr).send_qmp(qmp_cfg)

else:    
    parser.print_help()
