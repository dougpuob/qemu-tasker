Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Force

$SCRIPT_PATH=$MyInvocation.MyCommand.Definition
$TASK_NAME="launch-qemu-tasker"
$QEMU_TASKER_DIR=(Join-Path $ENV:HOMEDRIVE $ENV:HOMEPATH qemu-takser.git)
$RUN_START_BAT=(Join-Path $ENV:HOMEDRIVE $ENV:HOMEPATH 'run-puppet-server.bat')
$RUN_START_PS1=(Join-Path $ENV:HOMEDRIVE $ENV:HOMEPATH 'run-puppet-server.ps1')

if (-Not (Get-ScheduledTask | Where-Object {$_.TaskName -like $TASK_NAME}))
{
  # ----------------------------------------------------------------------------
  # Register a scheduled task
  # ----------------------------------------------------------------------------
  $RUN_START_CONTENT = ("@ECHO OFF{0}pwsh -Command $RUN_START_PS1{1}PAUSE" -f [environment]::NewLine [environment]::NewLine)
  $RUN_START_CONTENT | Set-Content  -Path $RUN_START_BAT
  $Trigger= New-ScheduledTaskTrigger -AtStartup
  $User= "NT AUTHORITY\SYSTEM"
  $Action= New-ScheduledTaskAction -Execute $RUN_START_BAT
  Register-ScheduledTask -TaskName $TASK_NAME -Trigger $Trigger -User $User -Action $Action -RunLevel Highest -Force
}
else
{
  # ----------------------------------------------------------------------------
  # Prepare and execute qemu-tasker.py as a puppet server
  # ----------------------------------------------------------------------------
  if (-Not (Test-Path $QEMU_TASKER_DIR)) {
    mkdir $QEMU_TASKER_DIR
  }
  Push-Location $QEMU_TASKER_DIR

  # Clone the qemu-tasker project
  git clone https://github.com/dougpuob/qemu-tasker.git .
  git checkout feature-add-puppet-command

  # Become a puppet server
  $QEMU_TASKER_PY = (Join-Path $QEMU_TASKER_DIR src qemu-tasker.py)
  python $QEMU_TASKER_PY puppet

  Pop-Location
}
