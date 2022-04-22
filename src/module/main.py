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

from module.pyrc.rc import rcresult
from module.puppet_server import puppet_server
from module.puppet_client import puppet_client


class main():

    def __init__(self, parsed_args, governor_client_obj=None):
        self.input_args = parsed_args
        self.setting = None
        self.WORK_DIR = 'qemu-tasker'

        #
        # Objects
        #
        self.governor_client_obj = governor_client_obj


        #
        # Setup & Start logger
        #
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        prefix = '[%(asctime)s][%(levelname)s]' + \
                 '[%(filename)s!%(funcName)s:%(lineno)d] %(message)s'
        self.formatter = logging.Formatter(prefix, datefmt='%Y%m%d %H:%M:%S')

        # Setup log mechanism
        self.screen = logging.StreamHandler()
        self.screen.setLevel(logging.INFO)
        self.screen.setFormatter(self.formatter)

    def main(self):

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
            setting_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', self.input_args.setting))
            if os.path.exists(setting_filepath):
                self.setting = loadconfig(setting_filepath).get_data()
            else:
                assert_text = "Setting file is not found (setting_filepath={}) !!!".format(setting_filepath)
                logging.error(assert_text)
                return False

            # Server socket address information
            self.setting.Governor.Address = self.input_args.host
            self.setting.Governor.Port = self.input_args.port
            self.server_addr = config.socket_address(self.input_args.host,
                                                     self.input_args.port)

            # Puppet socket address information
            puppet_cmd_addr_info = config.socket_address(self.setting.Governor.Address,
                                                         self.setting.Puppet.Port.Cmd)


            # =========================================================================
            # Server daemon commands
            # =========================================================================

            if 'server' == self.input_args.command:

                # Log to file
                filename = datetime.datetime.now().strftime("qemu-tasker-server--%Y%m%d_%H%M%S.log")
                logfile = logging.FileHandler(os.path.join(logdir, filename))
                logfile.setLevel(logging.INFO)
                logfile.setFormatter(self.formatter)
                self.logger.addHandler(logfile)

                # Log to screen
                self.logger.addHandler(self.screen)

                # Print init log text
                logging.info('--------------------------------------------------------------------------------')
                logging.info("filename={}".format(filename))
                logging.info(self.input_args)

                # Start
                governor_server(self.setting).start()


            elif 'puppet' == self.input_args.command:

                # Log to file
                filename = datetime.datetime.now().strftime("qemu-tasker-puppet--%Y%m%d_%H%M%S.log")
                logfile = logging.FileHandler(os.path.join(logdir, filename))
                logfile.setLevel(logging.INFO)
                logfile.setFormatter(self.formatter)
                self.logger.addHandler(logfile)

                # Log to screen
                self.logger.addHandler(self.screen)

                # Print init log text
                logging.info('--------------------------------------------------------------------------------')
                logging.info("filename={}".format(filename))
                logging.info(self.input_args)

                # Start
                puppet_server(self.setting).start()


            else:

                # =========================================================================
                # Control commands
                # =========================================================================

                # Log to file
                filename = datetime.datetime.now().strftime("qemu-tasker-client--%Y%m%d_%H%M%S.log")
                logfile = logging.FileHandler(os.path.join(logdir, filename))
                logfile.setLevel(logging.INFO)
                logfile.setFormatter(self.formatter)
                self.logger.addHandler(logfile)

                # Log to screen
                if not self.input_args.jsonreport:
                    self.logger.addHandler(self.screen)

                # Print init log text
                logging.info('--------------------------------------------------------------------------------')
                logging.info("filename={}".format(filename))
                logging.info(self.input_args)

                # Start
                if 'info' == self.input_args.command:
                    # Create a INFO command request
                    cmd_data = config.info_command_request_data()
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().info, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)

                elif 'start' == self.input_args.command:
                    assert self.input_args.config, "Please specific a config file !!!"

                    # Create a START command request
                    config_start_data = config.config().toCLASS(json.dumps(json.load(open(self.input_args.config))))
                    cmd_data = config.start_command_request_data(config_start_data.longlife,
                                                                 config_start_data.qcow2filename,
                                                                 config_start_data.cmd)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().start, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)


                elif 'kill' == self.input_args.command:
                    # Create a KILL command request
                    cmd_data = config.kill_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().kill, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)


                elif 'qmp' == self.input_args.command:
                    # Create a QMP command request
                    cmd_data = config.qmp_command_request_data(self.input_args.taskid,
                                                                    self.input_args.execute,
                                                                    self.input_args.argsjson,
                                                                    self.input_args.base64)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().qmp, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)


                elif 'status' == self.input_args.command:
                    # Create a STATUS command request
                    cmd_data = config.status_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().status, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)


                elif 'push' == self.input_args.command:
                    # Create a PUSH command request
                    cmd_data = config.push_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().push, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)


                elif 'signal' == self.input_args.command:
                    # Create a SIGNAL command request
                    cmd_data = config.signal_command_request_data(self.input_args.taskid)
                    response_capsule = governor_client(self.server_addr).send_control_command(config.command_kind().signal, cmd_data, self.input_args.jsonreport)
                    process_capsule(self.input_args, response_capsule)


                # =========================================================================
                # Puppet commands
                # =========================================================================

                elif 'execute' == self.input_args.command:
                    pup_client = self.get_puppet_client(self.input_args.taskid)
                    result: rcresult = pup_client.execute(self.input_args.program,
                                                          self.input_args.argument,
                                                          self.input_args.workdir)
                    response_capsule = config.execute_command_response_data(config.action_kind().response,
                                                                            config.command_kind().execute,
                                                                            data=result.data)
                    process_capsule(self.input_args, response_capsule)

                elif 'list' == self.input_args.command:
                    pup_client = self.get_puppet_client(self.input_args.taskid)
                    result: rcresult = pup_client.list(self.input_args.dstdir)
                    response_capsule = config.execute_command_response_data(config.action_kind().response,
                                                                            config.command_kind().list,
                                                                            data=result.data)
                    process_capsule(self.input_args, response_capsule)

                elif 'upload' == self.input_args.command:
                    pup_client = self.get_puppet_client(self.input_args.taskid)
                    result: list = pup_client.upload(self.input_args.files,
                                                         self.input_args.dstdir)
                    response_capsule = config.execute_command_response_data(config.action_kind().response,
                                                                            config.command_kind().upload,
                                                                            data=result)
                    process_capsule(self.input_args, response_capsule)

                elif 'download' == self.input_args.command:
                    pup_client = self.get_puppet_client(self.input_args.taskid)
                    result: rcresult = pup_client.download(self.input_args.files,
                                                           self.input_args.dstdir)
                    response_capsule = config.execute_command_response_data(config.action_kind().response,
                                                                            config.command_kind().download,
                                                                            data=result.data)
                    process_capsule(self.input_args, response_capsule)

                # =========================================================================
                # Unknown
                # =========================================================================

                else:
                    cmdargs().print_help()


        except Exception as e:
            logging.exception(e)


    def send_governor_status_command(self, gov_client:governor_client, taskid:int):
        cmd_data = config.status_command_request_data(taskid)
        response_capsule = gov_client.send_control_command(config.command_kind().status, cmd_data, None)
        return response_capsule


    def get_puppet_client(self, taskid:int):
        # Query status info
        status_resp_capsule:config.transaction_capsule = self.send_governor_status_command(governor_client(self.server_addr), taskid)
        if 0 == status_resp_capsule.result.errcode:
            status_resp_data:config.status_command_response_data = status_resp_capsule.data
            pup_client = puppet_client(taskid, self.WORK_DIR)

            pup_socket_info = config.socket_address(status_resp_data.server_info.socket_addr.address,
                                                    status_resp_data.forward.pup)
            pup_client.connect(pup_socket_info)
            return pup_client

        else:
            logging.error('Failed to get status command !!!')
            logging.error('result.errcode={}'.format(status_resp_capsule.result.errcode))
            logging.error('result.info_lines={}'.format(status_resp_capsule.result.info_lines))
            logging.error('result.error_lines={}'.format(status_resp_capsule.result.error_lines))
            return puppet_client(taskid)