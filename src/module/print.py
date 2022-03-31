# -*- coding: utf-8 -*-

import json
from module import config


class process_capsule():
    def __init__(self, cmdargs, json_capsule) -> None:
        if cmdargs.jsonreport and cmdargs.jsonreport == True:
            print(json.dumps(json_capsule.toJSON(), indent=2, sort_keys=True))
        else:
            print("[qemu-tasker] returned errcode: {}".format(json_capsule.result.errcode))


