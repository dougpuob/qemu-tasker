# -*- coding: utf-8 -*-

import logging
import json
import datetime
import os

from module import config
from module.main import main
from module.cmdparse import cmdargs
from module.loadconfig import loadconfig
from module.print import process_capsule

from module.governor_server import governor_server
from module.governor_client import governor_client

from module.puppet_server import puppet_server
from module.puppet_client import puppet_client


if __name__ == '__main__':
    parsed_args = cmdargs().get_parsed_args()
    governor_server_socket_info = config.socket_address(parsed_args.host, parsed_args.port)
    governor_client_obj = governor_client(governor_server_socket_info)
    main(parsed_args, governor_client_obj).main()
