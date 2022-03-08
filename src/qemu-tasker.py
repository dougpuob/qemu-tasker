# -*- coding: utf-8 -*-

import pathlib
import logging
import json
import os

from module import config
from module.server import server
from module.client import client
from module.cmdparse import cmdargs

cmdarg = cmdargs()
args = cmdarg.get_parsed_args()


#
# Start log
#
logging.basicConfig(filename='qemu-tasker.log',
                    level=logging.INFO,
                    format="[%(asctime)s][%(levelname)s] %(message)s",
                    datefmt='%Y-%m-%d-%H:%M:%S')

logging.info('--------------------------------------------------------------------------------')
logging.info(args)

socket_addr = config.socket_address(args.host, args.port)

try:
    if 'server' == args.command:
        server(socket_addr).start(args.filepool)

    elif 'start' == args.command:
        assert args.config, "Please specific a config file !!!"
        client_cfg = json.load(open(args.config))
        start_cfg = config.start_config(client_cfg)
        client(socket_addr).send_start(start_cfg, args.jsonreport)

    elif 'exec' == args.command:
        exec_arg = config.exec_argument(args.program, args.argument)
        exec_cmd = config.exec_command(args.taskid, exec_arg)
        exec_cfg = config.exec_config(exec_cmd.toJSON())
        client(socket_addr).send_exec(exec_cfg, args.jsonreport)

    elif 'kill' == args.command:
        kill_cmd = config.kill_command(args.taskid, args.killall)
        kill_cfg = config.kill_config(kill_cmd.toJSON())
        client(socket_addr).send_kill(kill_cfg, args.jsonreport)

    elif 'qmp' == args.command:
        argsjson = {}
        if args.argsfile and os.path.exists(args.argsfile):
            with open(args.argsfile, 'r') as txtfile:
                content = txtfile.read()   
                argsjson = json.loads(content)                
        elif args.argsjson:
            argsjson = json.loads(args.argsjson)
        else:        
            pass # this QMP command without argument
        
        qmp_cmd = config.qmp_command(args.taskid, args.execute, argsjson)
        qmp_cfg = config.qmp_config(qmp_cmd.toJSON())
        client(socket_addr).send_qmp(qmp_cfg, args.jsonreport)

    elif 'file' == args.command:
        file = config.file_command(args.taskid, args.sendfrom, args.sendto, args.pathfrom, args.pathto, args.config, args.port)
        file_cfg = config.file_config(file.toJSON())
        start_cfg = config.start_config(json.load(open(args.config)))
        ssh_info = config.ssh_conn_info(args.host, args.port, start_cfg.cmd.ssh_login.username, start_cfg.cmd.ssh_login.password)
        client(socket_addr).send_file(file_cfg, ssh_info, args.jsonreport)
        
    elif 'download' == args.command:
        dwload = config.download_command(args.taskid, args.files, args.saveto)
        dwload_cfg = config.download_config(dwload.toJSON())
        client(socket_addr).download_file(dwload_cfg, args.jsonreport)

    # elif 'upload' == args.command:
    #     file = config.file_command(args.taskid, args.sendfrom, args.sendto, args.pathfrom, args.pathto, args.config, args.port)
    #     file_cfg = config.file_config(file.toJSON())
    #     start_cfg = config.start_config(json.load(open(args.config)))
    #     ssh_info = config.ssh_conn_info(args.host, args.port, start_cfg.cmd.ssh_login.username, start_cfg.cmd.ssh_login.password)
    #     client(socket_addr).send_file(file_cfg, ssh_info, args.jsonreport)

    elif 'status' == args.command:
        stat = config.status_command(args.taskid)
        stat_cfg = config.status_config(stat.toJSON())
        client(socket_addr).send_status(stat_cfg, args.jsonreport)

    else:
        cmdarg.print_help()

except Exception as e:
    print(e)
    logging.exception(e)