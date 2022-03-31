from base64 import decode
import logging

from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

import subprocess
from time import sleep
from tokenize import Ignore

from inspect import currentframe, getframeinfo

from module import config

class execproc():
    def __init__(self):
        pass

    def enqueue_output(self, file, queue):
        for line in iter(file.readline, ''):
            queue.put(line)
        file.close()


    def read_popen_pipes(self, p):

        with ThreadPoolExecutor(2) as pool:
            q_stdout, q_stderr = Queue(), Queue()

            pool.submit(self.enqueue_output, p.stdout, q_stdout)
            pool.submit(self.enqueue_output, p.stderr, q_stderr)

            while True:

                if p.poll() is not None and q_stdout.empty() and q_stderr.empty():
                    break

                out_line = err_line = ''

                try:
                    out_line = str(q_stdout.get_nowait(), encoding='utf-8')
                except Empty:
                    pass
                try:
                    err_line = str(q_stderr.get_nowait(), encoding='utf-8')
                except Empty:
                    pass

                yield (out_line, err_line)



    def run(self, cmdargs:config.command_argument) -> config.command_return :

        cmdstr:str = cmdargs.program
        if cmdargs.argument:
             cmdstr = cmdstr + ' ' + cmdargs.argument
        logging.info("cmdstr={}".format(cmdstr))

        cmdret:config.command_return = config.command_return()

        try:
            proc = subprocess.Popen(cmdstr, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            if proc:
                cmdret.data = proc

                while True:
                    stdout_lines = [line.decode('utf-8', errors="ignore").rstrip() for line in proc.stdout.readlines()]
                    cmdret.info_lines.extend(stdout_lines)

                    stderr_lines = [line.decode('utf-8', errors="ignore").rstrip() for line in proc.stderr.readlines()]
                    cmdret.error_lines.extend(stderr_lines)

                    cmdret.errcode = proc.wait(1)
                    if (len(stderr_lines) == 0) and \
                    (len(stdout_lines) == 0):
                        break

        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            cmdret.errcode = -1
            cmdret.error_lines.append("exception={0}".format(e))
            cmdret.error_lines.append("frameinfo.filename={0}".format(frameinfo.filename))
            cmdret.error_lines.append("frameinfo.lineno={0}".format(frameinfo.lineno))
            logging.exception(cmdret.error_lines)

        finally:
            return cmdret