# -*- coding: utf-8 -*-

import logging
import json
import datetime
import os

from module import config_next
from module.server import server
from module.client import client
from module.cmdparse import cmdargs


cmdarg = cmdargs()
args = cmdarg.get_parsed_args()


#
# Setup & Start logger
#
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s',
	                            datefmt='%Y%m%d %H:%M:%S')
screen = logging.StreamHandler()
screen.setLevel(logging.INFO)
screen.setFormatter(formatter)


socket_addr = config_next.socket_address(args.host, args.port)


#
# Processing input commands
#
try:

    #
    # Setup log path
    #
    logdir='data/log'
    if args.logdir:
        logdir = args.logdir

    if not os.path.exists(logdir):
        os.makedirs(logdir)


    # =========================================================================
    # Control commands
    # =========================================================================

    if 'server' == args.command:

        # Setup log mechanism
        logger.addHandler(screen)
        logging.info('--------------------------------------------------------------------------------')
        filename = datetime.datetime.now().strftime("qemu-tasker-server--%Y%m%d_%H%M%S.log")
        logging.info("filename={}".format(filename))

        logfile = logging.FileHandler(os.path.join(logdir, filename))
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(formatter)
        logger.addHandler(logfile)
        logging.info(args)

        server(socket_addr).start(args.config)

    else:

        # Setup log mechanism
        filename = datetime.datetime.now().strftime("qemu-tasker-client--%Y%m%d_%H%M%S.log")
        logging.info("filename={}".format(filename))

        logfile = logging.FileHandler(os.path.join(logdir, filename))
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(formatter)
        logger.addHandler(logfile)
        logging.info(args)

        if 'info' == args.command:
            # Create a INFO command request
            cmd_data = config_next.info_command_request_data()
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().info, cmd_data, args.jsonreport)


        elif 'start' == args.command:
            assert args.config, "Please specific a config file !!!"

            # Create a START command request
            config_start_data = config_next.config().toCLASS(json.dumps(json.load(open(args.config))))
            cmd_data = config_next.start_command_request_data(config_start_data.longlife,
                                                            config_start_data.qcow2filename,
                                                            config_start_data.ssh,
                                                            config_start_data.cmd)
            # Update arguments from command line
            if args.host:
                cmd_data.ssh.target.address = args.host
            if args.port:
                cmd_data.ssh.target.port = args.port
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().start, cmd_data, args.jsonreport)


        elif 'kill' == args.command:
            # Create a KILL command request
            cmd_data = config_next.kill_command_request_data(args.taskid)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().kill, cmd_data, args.jsonreport)


        elif 'exec' == args.command:
            # Create a EXEC command request
            cmd_data = config_next.exec_command_request_data(args.taskid,
                                                            args.program,
                                                            args.argument,
                                                            args.base64)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().exec, cmd_data, args.jsonreport)


        elif 'qmp' == args.command:
            # Create a QMP command request
            cmd_data = config_next.qmp_command_request_data(args.taskid,
                                                            args.execute,
                                                            args.argsjson,
                                                            args.base64)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().qmp, cmd_data, args.jsonreport)


        elif 'status' == args.command:
            # Create a STATUS command request
            cmd_data = config_next.status_command_request_data(args.taskid)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().status, cmd_data, args.jsonreport)


        # =========================================================================
        # File transfer commands
        # =========================================================================

        elif 'list' == args.command:
            # Create a LIST command request
            cmd_data = config_next.list_command_request_data(args.taskid, args.dstdir)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_transfer_command(config_next.command_kind().list, cmd_data, args.jsonreport)

        elif 'upload' == args.command:
            # Create a UPLOAD command request
            cmd_data = config_next.upload_command_request_data(args.taskid, args.files, args.dstdir)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_transfer_command(config_next.command_kind().upload, cmd_data, args.jsonreport)

        elif 'download' == args.command:
            # Create a DOWNLOAD command request
            cmd_data = config_next.download_command_request_data(args.taskid, args.files, args.dstdir)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_transfer_command(config_next.command_kind().download, cmd_data, args.jsonreport)


        # =========================================================================
        # Synchronization commands
        # =========================================================================
        elif 'push' == args.command:
            # Create a PUSH command request
            cmd_data = config_next.push_command_request_data(args.taskid)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().push, cmd_data, args.jsonreport)

        elif 'signal' == args.command:
            # Create a SIGNAL command request
            cmd_data = config_next.signal_command_request_data(args.taskid)
            logging.info("[qemu-tasker.py] cmd_data={}".format(cmd_data.toTEXT()))
            client(socket_addr).send_control_command(config_next.command_kind().signal, cmd_data, args.jsonreport)


        # =========================================================================
        # Unknown
        # =========================================================================

        else:
            cmdarg.print_help()


except Exception as e:
    logging.exception(e)