import argparse
import pathlib
import logging
import signal
import sys

from module import socket
from module import config
from module import command


TASK_STATUS = command._task_status()


parent_parser = argparse.ArgumentParser(add_help=False)
parser = argparse.ArgumentParser(add_help=True) 

# create sub-parser
subparsers = parser.add_subparsers(dest="command")

# subcommand start                                                                  
parser_start = subparsers.add_parser('server', parents = [parent_parser], help='start a server daemon')

# subcommand info
parser_info = subparsers.add_parser('info', parents = [parent_parser], help='fetch current daemon information')

# subcommand start
parser_start = subparsers.add_parser('start', parents = [parent_parser], help='launch a QEMU achine instance')
parser_start.add_argument('-C', '--config', required=True)
parser_start.add_argument('-T', '--test',  action='store_true')

# subcommand kill
parser_kill = subparsers.add_parser('kill', parents = [parent_parser], help='kill the specific QEMU machine instance')
parser_kill.add_argument('-T', '--taskid', type=int, required=True)

# subcommand exec
parser_exec = subparsers.add_parser('exec', parents = [parent_parser], help='execute a specific command at guest operating system')
parser_exec.add_argument('-T', '--taskid', type=int, required=True)
parser_exec.add_argument('-P', '--program', required=True)
parser_exec.add_argument('-A', '--arguments')

# subcommand qmp
parser_exec = subparsers.add_parser('qmp', parents = [parent_parser], help='execute a specific QMP command on host QEMU machine')
parser_exec.add_argument('-T', '--taskid', type=int, required=True)
parser_exec.add_argument('-E', '--execute', required=True,
                                            choices=[# qmp-commands.hx
                                                     'quit',
                                                     'stop',
                                                     'cont',
                                                     'resume',
                                                     'system_wakeup',
                                                     'system_reset',
                                                     'system_powerdown',
                                                     'inject-nmi',
                                                     'migrate_cancel',
                                                     'query-dump',
                                                     'query-fdsets',
                                                     'qmp_capabilities', 
                                                     'query-tpm',
                                                     'query-tpm-models',
                                                     'query-tpm-types',
                                                     'rtc-reset-reinjection',
                                                     'query-gic-capabilities',
                                                     'query-hotpluggable-cpus',
                                                     'query-measurements',
                                                     'query-status', 
                                                     'query-commands'])
parser_exec.add_argument('-A', '--arguments')

# subcommand query
parser_query = subparsers.add_parser('query', parents = [parent_parser], help='query information from the QEMU machine instance')
parser_query.add_argument('-T', '--taskid')

args = parser.parse_args()
print(args)

logging.basicConfig(filename='default.log', 
                    level=logging.INFO,
                    format="[%(asctime)s][%(levelname)s] %(message)s",
                    datefmt='%Y-%m-%d-%H:%M:%S')

logging.info('--------------------------------------------------------------------------------')
logging.info(args)

config_path = pathlib.Path.joinpath(pathlib.Path(__file__).parent.absolute(), 'config/config.json')
config_data = config.command_config().load_file(config_path)
logging.info("Config Content: " + str(config_data))

host_ip = config_data['host']['ip']
host_port = config_data['host']['port']
host_info = command.host_information(host_ip, host_port)


if 'server' == args.command:
    socket.server(host_ip, host_port).start()

elif 'start' == args.command:
    assert args.config, "Please specific a config file !!!"
    cmd_cfg = config.start_command_config()
    cmd_cfg.load_config_from_file(args.config)
    if args.test:
        taskid:int = 10000
        task_inst = command.qemu_machine(host_info, taskid, cmd_cfg)
    else:
        socket.client(host_ip, host_port).exec_start_cmd(cmd_cfg)

elif 'info' == args.command:
    print('info')

elif 'kill' == args.command:
    cmd_cfg = config.kill_command_config()
    cmd_cfg.load_config( {"taskid" : args.taskid})
    socket.client(host_ip, host_port).exec_kill_cmd(cmd_cfg)

elif 'exec' == args.command:    
    cmd_cfg = config.exec_command_config()
    input_args = []
    if args.arguments:
        input_args.extend(args.arguments.split(' '))
    cmd_cfg.load_config( {"taskid" : args.taskid,
                          "program": args.program,
                          "arguments": input_args })
    socket.client(host_ip, host_port).exec_exec_cmd(cmd_cfg)

elif 'qmp' == args.command:    
    cmd_cfg = config.qmp_command_config()
    cmd_cfg.load_config( {"taskid" : args.taskid,
                          "execute": args.execute,
                          "arguments": args.arguments })
    socket.client(host_ip, host_port).exec_qmp_cmd(cmd_cfg)

elif 'query' == args.command:
    print('query')

else:    
    parser.print_help()
