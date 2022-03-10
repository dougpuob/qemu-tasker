# -*- coding: utf-8 -*-

import pathlib
import logging
import json
import os
import base64

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
        exec_cmd = config.exec_command(args.taskid, exec_arg, args.base64)
        exec_cfg = config.exec_config(exec_cmd.toJSON())
        client(socket_addr).send_exec(exec_cfg, args.jsonreport)

    elif 'kill' == args.command:
        kill_cmd = config.kill_command(args.taskid, args.killall)
        kill_cfg = config.kill_config(kill_cmd.toJSON())
        client(socket_addr).send_kill(kill_cfg, args.jsonreport)

    elif 'qmp' == args.command:
        qmp_cmd = config.qmp_command(args.taskid, args.execute, args.argsjson, args.base64)
        qmp_cfg = config.qmp_config(qmp_cmd.toJSON())
        client(socket_addr).send_qmp(qmp_cfg, args.jsonreport)

    elif 'push' == args.command:
        push_cmd = config.push_command(args.taskid)
        push_cfg = config.push_config(push_cmd.toJSON())
        client(socket_addr).send_push(push_cfg, args.jsonreport)

    elif 'status' == args.command:
        stat = config.status_command(args.taskid)
        stat_cfg = config.status_config(stat.toJSON())
        client(socket_addr).send_status(stat_cfg, args.jsonreport)

    elif 'list' == args.command:
        list_cmd = config.list_command(args.taskid, args.dirpath)
        list_cfg = config.list_config(list_cmd.toJSON())
        client(socket_addr).run_list(list_cfg, args.jsonreport)

    elif 'download' == args.command:
        list_cmd = config.download_command(args.taskid, args.files, args.dirpath)
        list_cfg = config.download_config(list_cmd.toJSON())
        client(socket_addr).run_download(list_cfg, args.jsonreport)

    elif 'upload' == args.command:
        upload = config.upload_command(args.taskid, args.files, args.dirpath)
        upload_cfg = config.upload_config(upload.toJSON())
        client(socket_addr).run_upload(upload_cfg, args.jsonreport)

    else:
        cmdarg.print_help()

except Exception as e:
    print(e)
    logging.exception(e)