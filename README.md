# qemu-tasker

The `qemu-tasker` project is a server-client program in Python which manage QEMU instances and communicate with them from the client side by commands. This project is inspired by implementing system testing in continuous integration (CI). It launch QEMU processes then connect QMP to the backend of QEMU and SSH to the guest operating system, then collect system resources by killing those processes in time, which is an option in config when launching.

The `server` command to start a daemon as a server manage all QEMU instances and send/receive commands from clients; the `start` command to launch a QEMU program, options for QEMU in a JSON config file. the server will response you an unique <TASKID> to identify the QEMU process; the `kill` command to kill a QEMU instance by its <TASKID>; the `exec` command to execute command by SSH; the `qmp` command to communicate with QEMU Machie Protocol(QMP), of cause you can send HMP via QMP.

![Figure](doc/figure-commands.png)

![Figure](doc/figure-connections.png)


----------

### Requirements

1. A Linux machine as the server which should support KVM.
2. Guest operating system installed QCOW2 images.
3. Setup OpenSSH server in those guest operating system images.
4. Create your own start config json file, reference to `src/qemu-taskcfg.json` in this project. Suggest to add `snapshot=on` at the drive option, like `"-drive", "file=windows-10-20h2.qcow2,format=qcow2,snapshot=on"`.


``` bash
pip3 install psutil
pip3 install ssh2-python
```

----------

### Quick Start
The server IP is `172.17.100.17`.

#### Server side:
1. Start the server.
   - `python3 qemu-tasker.py --host 172.17.100.17 server --config config.json`

#### Local side:
1. Query server information.
   - `python3 qemu-tasker.py --host 172.17.100.17 info`
1. Start an QEMU machine.
   - `python3 qemu-tasker.py --host 172.17.100.17 start --config qemu-taskcfg-01.json`
1. Execute a command on Guest OS.
   - `python3 qemu-tasker.py --host 172.17.100.17 exec --taskid 10010 --program ipconfig`

----------

## Commands

```
❯ python3 qemu-tasker.py --help

usage: qemu-tasker.py [-h] [-H HOST] [-P PORT] [-J] [-V] {server,start,kill,
exec,qmp,list,download,upload,push,status,info} ...

positional arguments:
  {server,start,kill,exec,qmp,list,download,upload,push,status,info}
    server              start a server daemon
    start               launch a QEMU achine instance
    kill                kill the specific QEMU machine instance
    exec                execute a specific command at guest operating system
    qmp                 execute a specific QMP command
    list                list files from local to guest
    download            download files from guest to local
    upload              upload files from local to guest
    push                update files from local to guest
    status              query a specific QEMU status
    info                get server system information

optional arguments:
  -h, --help            show this help message and exit
  -H HOST, --host HOST
  -P PORT, --port PORT
  -J, --jsonreport
  -V, --verbose
```

----------

## Examples

### Server
``` bash
❯ python3 qemu-tasker.py --host 172.17.100.17 server \
                         --config src/config.json
```

### Info
``` bash
❯ python3 qemu-tasker.py --host 172.17.100.17 \
                         --jsonreport \
                         info
{
  "response": {
    "command": "info",
    "data": {
      "errcode": 0,
      "images": [
        "abc.qcow2",
        "windows-10-20h2.qcow2"
      ],
      "instances": "",
      "result": true,
      "stderr": [],
      "stdout": [],
      "variables": {
        "SERVER_PUSHPOOL_DIR": "./pushpool",
        "SERVER_QCOW2_IMAGE_DIR": "/home/dougpuob/workspace/qemu-runner/"
      }
    }
  }
}

```

### Start
``` bash
❯ python3 qemu-tasker.py --host 172.17.100.17 \
                         --jsonreport \
                         start \
                         --config qemu-taskcfg.json
{
  "response": {
    "command": "start",
    "data": {
      "cwd": "qemu-tasker",
      "errcode": 0,
      "fwd_ports": {
        "qmp": 10051,
        "ssh": 10052
      },
      "os": "unknown",
      "result": true,
      "stderr": [],
      "stdout": [],
      "taskid": 10050
    }
  }
}

```

### Exec
``` bash
❯ python3 qemu-tasker.py --host 172.17.100.17 \
                         --jsonreport \
                         exec \
                         --taskid 10060 \
                         --program "ipconfig" \
                         --argument="-all"
{
  "response": {
    "command": "exec",
    "data": {
      "errcode": 0,
      "result": true,
      "stderr": [],
      "stdout": [
        "",
        "Windows IP Configuration",
        "",
        "   Host Name . . . . . . . . . . . . : DESKTOP-I9TKP5J",
        "   Primary Dns Suffix  . . . . . . . : ",
        "   Node Type . . . . . . . . . . . . : Hybrid",
        "   IP Routing Enabled. . . . . . . . : No",
        "   WINS Proxy Enabled. . . . . . . . : No",
        "",
        "Ethernet adapter Ethernet Instance 0:",
        "",
        "   Connection-specific DNS Suffix  . : ",
        "   Description . . . . . . . . . . . : Intel(R) PRO/1000 MT Network Connection #2",
        "   Physical Address. . . . . . . . . : 52-54-00-12-34-56",
        "   DHCP Enabled. . . . . . . . . . . : Yes",
        "   Autoconfiguration Enabled . . . . : Yes",
        "   Site-local IPv6 Address . . . . . : fec0::4ce8:6b94:da87:28d3%1(Preferred) ",
        "   Link-local IPv6 Address . . . . . : fe80::4ce8:6b94:da87:28d3%14(Preferred) ",
        "   IPv4 Address. . . . . . . . . . . : 10.0.2.15(Preferred) ",
        "   Subnet Mask . . . . . . . . . . . : 255.255.255.0",
        "   Lease Obtained. . . . . . . . . . : Friday, March 11, 2022 6:50:28 AM",
        "   Lease Expires . . . . . . . . . . : Saturday, March 12, 2022 6:50:28 AM",
        "   Default Gateway . . .",
        " . . . . . . : fe80::2%14",
        "                                       10.0.2.2",
        "   DHCP Server . . . . . . . . . . . : 10.0.2.2",
        "   DHCPv6 IAID . . . . . . . . . . . : 257053696",
        "   DHCPv6 Client DUID. . . . . . . . : 00-01-00-01-29-5F-7C-32-52-54-00-12-34-56",
        "   DNS Servers . . . . . . . . . . . : 10.0.2.3",
        "   NetBIOS over Tcpip. . . . . . . . : Enabled"
      ],
      "taskid": 10060
    }
  }
}

```

### QMP

``` bash
❯ python3 qemu-tasker.py --host 172.17.100.17 \
                         --jsonreport \
                         qmp \
                         --taskid 10060 \
                         --execute human-monitor-command \
                         --argsjson='''{"command-line" : "info version" }'''
{
  "response": {
    "command": "qmp",
    "data": {
      "errcode": 0,
      "result": true,
      "stderr": "",
      "stdout": {
        "return": "6.2.50v6.2.0-996-g78a5f4fe83\r\n"
      },
      "taskid": 10060
    }
  }
}

```

``` bash
❯ python3 qemu-tasker.py --host 172.17.100.17 \
                               --jsonreport \
                               qmp \
                               --taskid 10060 \
                               --execute human-monitor-command \
                               --argsjson='''{"command-line" : "savevm snapshot01" }'''
{
  "response": {
    "command": "qmp",
    "data": {
      "errcode": 0,
      "result": true,
      "stderr": "",
      "stdout": {
        "return": ""
      },
      "taskid": 10060
    }
  }
}

```

``` powershell
PS> python ./qemu-tasker.py --host 172.17.100.17 qmp \
                            --taskid 10010 \
                            --execute human-monitor-command \
                            --argsjson='{\"command-line\":\"device_add usb-winusb,id=winusb-01,pcap=winusb-01.pcap\"}'
```

### List
### Upload
### Download
### Push
### Status

----------
END