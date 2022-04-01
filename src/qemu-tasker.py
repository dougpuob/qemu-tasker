# -*- coding: utf-8 -*-

import logging
import json
import datetime
import os

from module import config
from module.server import server
from module.puppet import puppet_server, puppet_client
from module.client import client
from module.loadconfig import loadconfig
from module.cmdparse import cmdargs
from module.print import process_capsule



cmdarg = cmdargs()
input_args = cmdarg.get_parsed_args()


#
# Setup & Start logger
#
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s',
	                            datefmt='%Y%m%d %H:%M:%S')

# Setup log mechanism
screen = logging.StreamHandler()
screen.setLevel(logging.INFO)
screen.setFormatter(formatter)
logger.addHandler(screen)


#
# Processing input commands
#
try:

    #
    # Setup log path
    #
    logdir='data/log'
    if input_args.logdir:
        logdir = input_args.logdir

    if not os.path.exists(logdir):
        os.makedirs(logdir)

    # Load JSON config file
    settings_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), input_args.settings))
    settings = loadconfig(settings_filepath).get_data()

    # Server socket address information
    server_addr = config.socket_address(input_args.host, input_args.port)

    # Puppet socket address information
    puppet_cmd_addr_info = config.socket_address(settings.Puppet.Host.Address, settings.Puppet.Host.Port.Cmd)
    puppet_ftp_addr_info = config.socket_address(settings.Puppet.Host.Address, settings.Puppet.Host.Port.Ftp)


    # =========================================================================
    # Daemon commands
    # =========================================================================

    if 'server' == input_args.command:

        logging.info('--------------------------------------------------------------------------------')
        filename = datetime.datetime.now().strftime("qemu-tasker-server--%Y%m%d_%H%M%S.log")
        logging.info("filename={}".format(filename))

        logfile = logging.FileHandler(os.path.join(logdir, filename))
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(formatter)
        logger.addHandler(logfile)
        logging.info(input_args)

        server(server_addr).start(input_args.config)


    elif 'puppet' == input_args.command:

        logger.addHandler(screen)
        logging.info('--------------------------------------------------------------------------------')
        filename = datetime.datetime.now().strftime("qemu-tasker-puppet--%Y%m%d_%H%M%S.log")
        logging.info("filename={}".format(filename))

        logfile = logging.FileHandler(os.path.join(logdir, filename))
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(formatter)
        logger.addHandler(logfile)
        logging.info(input_args)

        puppet_server(settings).start()


    else:

        # =========================================================================
        # Control commands
        # =========================================================================

        # Setup log mechanism
        filename = datetime.datetime.now().strftime("qemu-tasker-client--%Y%m%d_%H%M%S.log")


        logfile = logging.FileHandler(os.path.join(logdir, filename))
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(formatter)
        logger.addHandler(logfile)

        if not input_args.jsonreport:
            logging.info("filename={}".format(filename))
            logging.info(input_args)

        if 'info' == input_args.command:
            # Create a INFO command request
            cmd_data = config.info_command_request_data()
            client(server_addr).send_control_command(config.command_kind().info, cmd_data, input_args.jsonreport)


        elif 'start' == input_args.command:
            assert input_args.config, "Please specific a config file !!!"

            # Create a START command request
            config_start_data = config.config().toCLASS(json.dumps(json.load(open(input_args.config))))
            cmd_data = config.start_command_request_data(config_start_data.longlife,
                                                            config_start_data.qcow2filename,
                                                            config_start_data.ssh,
                                                            config_start_data.cmd)
            # Update arguments from command line
            if input_args.host:
                cmd_data.ssh.target.address = input_args.host
            if input_args.port:
                cmd_data.ssh.target.port = input_args.port
            client(server_addr).send_control_command(config.command_kind().start, cmd_data, input_args.jsonreport)


        elif 'kill' == input_args.command:
            # Create a KILL command request
            cmd_data = config.kill_command_request_data(input_args.taskid)
            client(server_addr).send_control_command(config.command_kind().kill, cmd_data, input_args.jsonreport)


        elif 'exec' == input_args.command:
            # Create a EXEC command request
            cmd_data = config.exec_command_request_data(input_args.taskid,
                                                            input_args.program,
                                                            input_args.argument,
                                                            input_args.base64)
            client(server_addr).send_control_command(config.command_kind().exec, cmd_data, input_args.jsonreport)


        elif 'qmp' == input_args.command:
            # Create a QMP command request
            cmd_data = config.qmp_command_request_data(input_args.taskid,
                                                            input_args.execute,
                                                            input_args.argsjson,
                                                            input_args.base64)
            client(server_addr).send_control_command(config.command_kind().qmp, cmd_data, input_args.jsonreport)


        elif 'status' == input_args.command:
            # Create a STATUS command request
            cmd_data = config.status_command_request_data(input_args.taskid)
            client(server_addr).send_control_command(config.command_kind().status, cmd_data, input_args.jsonreport)


        # =========================================================================
        # Puppet commands
        # =========================================================================

        elif 'execute' == input_args.command:
            cmd_data = config.execute_command_request_data(input_args.taskid,
                                                           input_args.program,
                                                           input_args.argument,
                                                           input_args.base64)
            response_capsule = puppet_client(puppet_cmd_addr_info).request_puppet_command(config.command_kind().execute, cmd_data)
            process_capsule(input_args, response_capsule)

        elif 'list' == input_args.command:
            cmd_data = config.list_command_request_data(input_args.taskid, input_args.dstdir)
            response_capsule = puppet_client(puppet_cmd_addr_info).request_puppet_command(config.command_kind().list, cmd_data)
            process_capsule(input_args, response_capsule)

        elif 'upload' == input_args.command:
            cmd_data = config.upload_command_request_data(input_args.taskid, input_args.files, input_args.dstdir)
            response_capsule = puppet_client(puppet_cmd_addr_info).request_puppet_command(config.command_kind().upload, cmd_data)
            process_capsule(input_args, response_capsule)

        elif 'download' == input_args.command:
            cmd_data = config.download_command_request_data(input_args.taskid, input_args.files, input_args.dstdir)
            response_capsule = puppet_client(puppet_cmd_addr_info).request_puppet_command(config.command_kind().download, cmd_data)
            process_capsule(input_args, response_capsule)


        # =========================================================================
        # Synchronization commands
        # =========================================================================

        elif 'push' == input_args.command:
            # Create a PUSH command request
            cmd_data = config.push_command_request_data(input_args.taskid)
            client(server_addr).send_control_command(config.command_kind().push, cmd_data, input_args.jsonreport)

        elif 'signal' == input_args.command:
            # Create a SIGNAL command request
            cmd_data = config.signal_command_request_data(input_args.taskid)
            client(server_addr).send_control_command(config.command_kind().signal, cmd_data, input_args.jsonreport)


        # =========================================================================
        # Unknown
        # =========================================================================

        else:
            cmdarg.print_help()


except Exception as e:
    logging.exception(e)

