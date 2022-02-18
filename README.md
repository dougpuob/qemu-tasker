# README



----------

## Commands

```
usage: qemu-tasker.py [-h] {server,start,kill,exec,qmp} ...

positional arguments:
  {server,start,kill,exec,qmp}
    server           start a server daemon
    start              launch a QEMU achine instance
    kill                kill the specific QEMU machine instance
    exec             execute a specific command at guest operating system
    qmp             execute a specific QMP command

optional arguments:
  -h, --help       show this help message and exit
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
python3 qemu-tasker.py qmp --taskid 10010 --execute human-monitor-command --argsjson='''{"command-line" : "info version" }'''
```

``` bash
python3 qemu-tasker.py qmp --taskid 10010 --execute human-monitor-command --argsjson='''{"command-line" : "savevm snapshot01" }'''
```