# -*- coding: utf-8 -*-

import json
from module import config


class process_capsule():
    def __init__(self, cmdargs, response_capsule:config.transaction_capsule) -> None:
        if cmdargs.jsonreport and cmdargs.jsonreport == True:
            print(json.dumps(response_capsule.toJSON(), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] returned errcode: {}".format(response_capsule.result.errcode))
            print("json_capsule={}".format(response_capsule))


