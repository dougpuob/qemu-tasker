$SCRIPT_PATH=$MyInvocation.MyCommand.Definition
$TASK_NAME="launch-qemu-tasker"
$QEMU_TASKER_DIR=(Join-Path $ENV:HOMEDRIVE $ENV:HOMEPATH qemu-takser.git)

if (-Not (Get-ScheduledTask | Where-Object {$_.TaskName -like $TASK_NAME})) {
  $QEMU_TASKER_PY=(Join-Path $QEMU_TASKER_DIR src qemu-takser.py)
  $Trigger= New-ScheduledTaskTrigger -AtStartup
  $User= "NT AUTHORITY\SYSTEM"
  $Action= New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument ("$QEMU_TASKER_PY {0}" -f "puppet")
  Register-ScheduledTask -TaskName $TASK_NAME -Trigger $Trigger -User $User -Action $Action -RunLevel Highest –Force # Specify the name of the task
} else {

  if (-Not (Test-Path $QEMU_TASKER_DIR)) {
	mkdir $QEMU_TASKER_DIR
  }
  Push-Location $QEMU_TASKER_DIR


  # Clone the qemu-tasker project
  git clone https://github.com/dougpuob/qemu-tasker.git .
  git checkout feature-add-puppet-command


  # Become a puppet server
  python ./src/qemu-tasker.py puppet


  Pop-Location
}
