param(
    [string]$Distribution = "Ubuntu",
    [string]$TaskName = "ONNELLAB Codex Content Supply",
    [string]$DailyTime = "06:00"
)

$ErrorActionPreference = "Stop"
$wsl = Join-Path $env:WINDIR "System32\wsl.exe"
$repository = "/mnt/c/dev/onnel-content-engine"
$runner = "$repository/scripts/run_codex_content_supply.sh"
$arguments = "-d `"$Distribution`" -- bash -lc `"cd '$repository' && bash '$runner'`""
$action = New-ScheduledTaskAction -Execute $wsl -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Prepare qualified bilingual ONNELLAB content using the local Codex ChatGPT subscription login." `
    -Force | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State
    NextRunTime = $info.NextRunTime
    Distribution = $Distribution
    Runner = $runner
}
