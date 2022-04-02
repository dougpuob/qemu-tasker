# -*- coding: utf-8 -*-

import logging
import json
import datetime
import os

from module import config
from module.cmdparse import cmdargs
from module.loadconfig import loadconfig
from module.print import process_capsule

from module.governor_server import governor_server
from module.governor_client import governor_client

from module.puppet_server import puppet_server
from module.puppet_client import puppet_client



class qemu_tasker():

    def __init__(self):
        self.cmdarg = cmdargs()
        self.input_args = self.cmdarg.get_parsed_args()


        #
        # Setup & Start logger
        #
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s',
                                        datefmt='%Y%m%d %H:%M:%S')

        # Setup log mechanism
        self.screen = logging.StreamHandler()
        self.screen.setLevel(logging.INFO)
        self.screen.setFormatter(self.formatter)
        self.logger.addHandler(self.screen)

        #
        # Runtime variables
        #
        self.settings = None
        self.server_addr = None


    def main(self):

        #
        # Processing input commands
        #
        try:

            #
            # Setup log path
            #
            logdir='data/log'
            if self.input_args.logdir:
                logdir = self.input_args.logdir

            if not os.path.exists(logdir):
                os.makedirs(logdir)

            # Load JSON config file
            settings_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), self.input_args.settings))
            self.settings = loadconfig(settings_filepath).get_data()

            # Server socket address information
            self.server_addr = config.socket_address(self.input_args.host, self.input_args.port)

            # Puppet socket address information
            puppet_cmd_addr_info = config.socket_address(self.settings.Puppet.Host.Address, self.settings.Puppet.Host.Port.Cmd)
            puppet_ftp_addr_info = config.socket_address(self.settings.Puppet.Host.Address, self.settings.Puppet.Host.Port.Ftp)


            # =========================================================================
            # Daemon commands
            # =========================================================================

            if 'server' == self.input_args.command:

                logging.info('--------------------------------------------------------------------------------')
                filename = datetime.datetime.now().strftime("qemu-tasker-server--%Y%m%d_%H%M%S.log")
                logging.info("filename={}".format(filename))

                logfile = logging.FileHandler(os.path.join(logdir, filename))
                logfile.setLevel(logging.INFO)
                logfile.setFormatter(self.formatter)
                self.logger.addHandler(logfile)
                logging.info(self.input_args)

                governor_server(self.server_addr).start(self.input_args.config)


            elif 'puppet' == self.input_args.command:

                self.logger.addHandler(self.screen)
                logging.info('--------------------------------------------------------------------------------')
                filename = datetime.datetime.now().strftime("qemu-tasker-puppet--%Y%m%d_%H%M%S.log")
                logging.info("filename={}".format(filename))

                logfile = logging.FileHandler(os.path.join(logdir, filename))
                logfile.setLevel(logging.INFO)
                logfile.setFormatter(self.formatter)
                self.logger.addHandler(logfile)
                logging.info(self.input_args)

                puppet_server(self.settings).start()


            else:

                # =========================================================================
                # Control commands
                # =========================================================================

                # Setup log mechanism
                filename = datetime.datetime.now().strftime("qemu-tasker-client--%Y%m%d_%H%M%S.log")


                logfile = logging.FileHandler(os.path.join(logdir, filename))
                logfile.setLevel(logging.INFO)
                logfile.setFormatter(self.formatter)
                self.logger.addHandler(logfile)

                if not self.input_args.jsonreport:
                    logging.info("filename={}".format(filename))
                    logging.info(self.input_args)

                if 'info' == self.input_args.command:
                    # Create a INFO command request
                    cmd_data = config.info_command_request_data()
                    governor_client(self.server_addr).send_control_command(config.command_kind().info, cmd_data, self.input_args.jsonreport)


                elif 'start' == self.input_args.command:
                    assert self.input_args.config, "Please specific a config file !!!"

                    # Create a START command request
                    config_start_data = config.config().toCLASS(json.dumps(json.load(open(self.input_args.config))))
                    cmd_data = config.start_command_request_data(config_start_data.longlife,
                                                                    config_start_data.qcow2filename,
                                                                    config_start_data.ssh,
                                                                    config_start_data.cmd)
                    # Update arguments from command line
                    if self.input_args.host:
                        cmd_data.ssh.target.address = self.input_args.host
                    if self.input_args.port:
                        cmd_data.ssh.target.port = self.input_args.port
                    governor_client(self.server_addr).send_control_command(config.command_kind().start, cmd_data, self.input_args.jsonreport)


                elif 'kill' == self.input_args.command:
                    # Create a KILL command request
                    cmd_data = config.kill_command_request_data(self.input_args.taskid)
                    governor_client(self.server_addr).send_control_command(config.command_kind().kill, cmd_data, self.input_args.jsonreport)


                elif 'exec' == self.input_args.command:
                    # Create a EXEC command request
                    cmd_data = config.exec_command_request_data(self.input_args.taskid,
                                                                    self.input_args.program,
                                                                    self.input_args.argument,
                                                                    self.input_args.base64)
                    governor_client(self.server_addr).send_control_command(config.command_kind().exec, cmd_data, self.input_args.jsonreport)


                elif 'qmp' == self.input_args.command:
                    # Create a QMP command request
                    cmd_data = config.qmp_command_request_data(self.input_args.taskid,
                                                                    self.input_args.execute,
                                                                    self.input_args.argsjson,
                                                                    self.input_args.base64)
                    governor_client(self.server_addr).send_control_command(config.command_kind().qmp, cmd_data, self.input_args.jsonreport)


                elif 'status' == self.input_args.command:
                    # Create a STATUS command request
                    cmd_data = config.status_command_request_data(self.input_args.taskid)
                    governor_client(self.server_addr).send_control_command(config.command_kind().status, cmd_data, self.input_args.jsonreport)


                # =========================================================================
                # Puppet commands
                # =========================================================================

                elif 'execute' == self.input_args.command:
                    # Query status info
                    cmd_data = config.status_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().status, cmd_data, None)
                    status_data:config.status_command_response_data = response_capsule.data

                    # Original command
                    cmd_data = config.execute_command_request_data(self.input_args.taskid,
                                                                self.input_args.program,
                                                                self.input_args.argument,
                                                                self.input_args.base64)
                    response_capsule = puppet_client(status_data.server_info.socket_addr).request_puppet_command(config.command_kind().execute, cmd_data)
                    process_capsule(self.input_args, response_capsule)

                elif 'list' == self.input_args.command:
                    # Query status info
                    cmd_data = config.status_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().status, cmd_data, None)
                    status_data:config.status_command_response_data = response_capsule.data

                    # Original command
                    cmd_data = config.list_command_request_data(self.input_args.taskid, self.input_args.dstdir)
                    response_capsule = puppet_client(status_data.server_info.socket_addr).request_puppet_command(config.command_kind().list, cmd_data)
                    process_capsule(self.input_args, response_capsule)

                elif 'upload' == self.input_args.command:
                    # Query status info
                    cmd_data = config.status_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().status, cmd_data, None)
                    status_data:config.status_command_response_data = response_capsule.data

                    # Original command
                    cmd_data = config.upload_command_request_data(self.input_args.taskid, self.input_args.files, self.input_args.dstdir)
                    response_capsule = puppet_client(status_data.server_info.socket_addr).request_puppet_command(config.command_kind().upload, cmd_data)
                    process_capsule(self.input_args, response_capsule)

                elif 'download' == self.input_args.command:
                    # Query status info
                    cmd_data = config.status_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().status, cmd_data, None)
                    status_data:config.status_command_response_data = response_capsule.data

                    # Original command
                    cmd_data = config.download_command_request_data(self.input_args.taskid, self.input_args.files, self.input_args.dstdir)
                    response_capsule = puppet_client(status_data.server_info.socket_addr).request_puppet_command(config.command_kind().download, cmd_data)
                    process_capsule(self.input_args, response_capsule)


                # =========================================================================
                # Synchronization commands
                # =========================================================================

                elif 'push' == self.input_args.command:
                    # Create a PUSH command request
                    cmd_data = config.push_command_request_data(self.input_args.taskid)
                    governor_client(self.server_addr).send_control_command(config.command_kind().push, cmd_data, self.input_args.jsonreport)

                elif 'signal' == self.input_args.command:
                    # Create a SIGNAL command request
                    cmd_data = config.signal_command_request_data(self.input_args.taskid)
                    governor_client(self.server_addr).send_control_command(config.command_kind().signal, cmd_data, self.input_args.jsonreport)


                # =========================================================================
                # Unknown
                # =========================================================================

                else:
                    self.cmdarg.print_help()


        except Exception as e:
            logging.exception(e)


    def send_governor_status_command(self, gov_server_socket_info:config.socket_address, taskid:int) -> config.status_command_response_data:
        cmd_data = config.status_command_request_data(taskid)
        response_capsule = governor_client(gov_server_socket_info).send_control_command(config.command_kind().status, cmd_data, None)
        status_data:config.status_command_response_data = response_capsule.data
        return status_data


if __name__ == '__main__':
    qemu_tasker().main()



