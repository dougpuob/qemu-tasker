# run-puppet-server.sh
if [ ! -d ~/qemu-tasker.git ]; then
    git clone https://github.com/dougpuob/qemu-tasker.git ~/qemu-tasker.git 
fi
python3 ~/qemu-tasker.git/src/qemu-tasker.py puppet
