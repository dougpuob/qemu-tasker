# README


## Commands

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