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
parser_start = subparsers.add_parser('server', parents = [parent_parser], help='start a QEMU-Tasker daemon')           

# subcommand info
parser_info = subparsers.add_parser('info', parents = [parent_parser], help='fetch current daemon information')

# subcommand task
parser_task = subparsers.add_parser('task', parents = [parent_parser], help='launch a QEMU achine instance')
parser_task.add_argument('-C', '--config')
parser_task.add_argument('-T', '--test',  action='store_true')

# subcommand kill
parser_kill = subparsers.add_parser('kill', parents = [parent_parser], help='kill the specific QEMU machine instance')
parser_kill.add_argument('-T', '--task')  

# subcommand exec
parser_exec = subparsers.add_parser('exec', parents = [parent_parser], help='execute a specific command at guest operating system')
parser_exec.add_argument('-T', '--task')
parser_exec.add_argument('-C', '--cmd')

# subcommand query
parser_query = subparsers.add_parser('query', parents = [parent_parser], help='query information from the QEMU machine instance')
parser_query.add_argument('-T', '--task')

args = parser.parse_args()
logging.basicConfig(filename='default.log', 
                    level=logging.INFO,
                    format="[%(asctime)s][%(levelname)s] %(message)s",
                    datefmt='%Y-%m-%d-%H:%M:%S')

logging.info('--------------------------------------------------------------------------------')
logging.info(args)

config_path = pathlib.Path.joinpath(pathlib.Path(__file__).parent.absolute(), 'config/config.json')
config_data = config.config().load_file(config_path)
logging.info("Config Content: " + str(config_data))

host_ip = config_data['host']['ip']
host_port = config_data['host']['port']
host_info = command.host_information(host_ip, host_port)

if 'server' == args.command:
    socket.server(host_ip, host_port).start()

elif 'task' == args.command:
    assert args.config, "Please specific a config file !!!"
    task_cfg = config.task_config()
    task_cfg.load_config_file(args.config)
    if args.test:
        taskid = 10000
        task_inst = command.task_instance(host_info, taskid, task_cfg)
    else:
        socket.client(host_ip, host_port).create_task(task_cfg)

elif 'info' == args.command:
    print('info')
elif 'kill' == args.command:
    print('kill')
elif 'exec' == args.command:
    socket.server(host_ip, host_port).send(args.task, args.cmd) 
elif 'query' == args.command:
    print('query')
else:    
    parser.print_help()
