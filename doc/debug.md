
# DEBUG

## Communicate with QEMU

``` bash
qemu-systemx86_64 \
    -m 4G \
    -smp 4 \
    -accel kvm \
    -usb -device usb-tablet \
    -drive windows-10-20h2.qcow2,format=qcow2,snapshot=on \
    -net nic,model=e1000,netdev=network0 \
    -netdev user,id=network0,hostfwd=tcp::10002-:22 \
    -monitor tcp::10001,server,nowait
```
- Send command to qemu-monitor
  - `echo "info snapshots" | socat - tcp:localhost:10001`
  - `echo "savevm snapshot02" | socat - tcp:localhost:10001`

- Send command to guest operating system (ssh)
  - `sshpass -p dougpuob ssh dougpuob@localhost -p 10002 'ipconfig'`
