$LOCAL_PATH="~/qemu-tasker.git"
mkdir $LOCAL_PATH
Push-Location $LOCAL_PATH


# Clone the qemu-tasker project
git clone https://github.com/dougpuob/qemu-tasker.git .
git checkout feature-add-puppet-command

# Become a puppet server
python ./src/qemu-tasker.py puppet


Pop-Location
