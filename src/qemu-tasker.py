# -*- coding: utf-8 -*-

import pathlib
import logging
import json
import sys

from module import config
from module.server import server
from module.client import client
from module.cmdparse import cmdargs


args = cmdargs().get_parsed_args()


#
# Start log
#
logging.basicConfig(filename='default.log', 
                    level=logging.INFO,
                    format="[%(asctime)s][%(levelname)s] %(message)s",
                    datefmt='%Y-%m-%d-%H:%M:%S')

logging.info('--------------------------------------------------------------------------------')
logging.info(args)

socket_addr = config.socket_address(args.host, args.port)

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
    qmp_cmd = config.qmp_command(args.taskid, args.execute, json.loads(args.argsjson))
    qmp_cfg = config.qmp_config(qmp_cmd.toJSON())
    client(socket_addr).send_qmp(qmp_cfg)

elif 'file' == args.command:
    file = config.file_command(args.taskid, args.kind, args.filepath, args.savepath, args.newdir, args.config, args.port)
    file_cfg = config.file_config(file.toJSON())
    client(socket_addr).send_file(file_cfg)    

else:    
    parser.print_help()
