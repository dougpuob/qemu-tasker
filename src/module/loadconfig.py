# -*- coding: utf-8 -*-

import os
import json
from module import config

class loadconfig():
  def __init__(self, config_path:str) -> object:
    self.object = None
    self.rawtext:str = ''
    if os.path.exists(config_path):
      with open(config_path) as f:
        json_data = json.load(f)
        rawtext = json.dumps(json_data, indent=2, sort_keys=True)
      self.object = config.config().toCLASS(rawtext)

  def get_data(self):
    return self.object