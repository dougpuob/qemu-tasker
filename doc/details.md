
# Details

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