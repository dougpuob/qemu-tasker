# README

The `qemu-tasker` project is a server-client program in Python which manage QEMU instances and communicate with them from the client side by commands. The `server` command to start a daemon as a server manage all QEMU instances and send/receive commands from clients; the `start` command to launch a QEMU program, options for QEMU in a JSON config file. the server will response you an unique <TASKID> to identify the QEMU process; the `kill` command to kill a QEMU instance by its <TASKID>; the `exec` command to execute command by SSH; the `qmp` command to communicate with QEMU Machie Protocol(QMP), of cause you can send HMP via QMP.

![Figure](doc/figure.png)

Make the `SSH` and `QMP` work, the `qemu-tasker` adds related QEMU options automatically when launch QEMU processes. You have to setup the SSH server in your operating system images, the username and password of SSH is in the config file.

``` python
def attach_qemu_device_qmp(self):
    self.is_qemu_device_attached_nic = True
    arg1 = ["-netdev", "user,id=network0,hostfwd=tcp::{}-:{}".format(self.fwd_ports.ssh, 22)]
    arg2 = ["-net", "nic,model=e1000,netdev=network0"]
    self.base_args.extend(arg1)
    self.base_args.extend(arg2)

def attach_qemu_device_qmp(self):
    if self.is_qemu_device_attached_qmp:
        return
    self.is_qemu_device_attached_qmp = True
    arg1 = ["-chardev", "socket,id=qmp,host={},port={}".format(self.socket_addr.addr, 
                                                               self.fwd_ports.qmp)]
    arg2 = ["-mon", "chardev=qmp,mode=control"]
    self.base_args.extend(arg1)
```


----------

## Commands

```
usage: qemu-tasker.py [-h] {server,start,kill,exec,qmp} ...

positional arguments:
  {server,start,kill,exec,qmp}
    server              start a server daemon
    start               launch a QEMU achine instance
    kill                kill the specific QEMU machine instance
    exec                execute a specific command at guest operating system
    qmp                 execute a specific QMP command

optional arguments:
  -h, --help            show this help message and exit
```

----------

## Examples

### Server
``` bash
python3 qemu-tasker.py server
```
### Start
``` bash
python3 qemu-tasker.py start --config config/qemu-taskcfg-01.json
```

### Exec
``` bash
python3 qemu-tasker.py exec --taskid 10010 --program "ipconfig" --arguments="-all"
```
### QMP

``` bash
python3 qemu-tasker.py qmp --taskid 10010 \
                           --execute human-monitor-command \
                           --argsjson='''{"command-line" : "info version" }'''
```

``` bash
python3 qemu-tasker.py qmp --taskid 10010 \
                           --execute human-monitor-command \
                           --argsjson='''{"command-line" : "savevm snapshot01" }'''
```