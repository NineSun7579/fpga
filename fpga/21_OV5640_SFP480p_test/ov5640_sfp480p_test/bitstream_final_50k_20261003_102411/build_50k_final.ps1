param([Parameter(Mandatory=$true)][string]$ArtifactDirectory, [switch]$ResumeCompiled, [switch]$ResumeRouted, [switch]$ResumeSta)
$ErrorActionPreference = 'Stop'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'
$python = 'C:\Users\NineSun\anaconda3\python.exe'
$runner = Join-Path $ArtifactDirectory 'build_50k_final.py'
# Use the production tool path: the archived copy is a review artifact, not a
# relocated executable whose ROOT calculation would point at a different tree.
$runner = Join-Path $PSScriptRoot 'build_50k_final.py'
Write-Host "PRODUCTION 50K ARTIFACT_DIRECTORY: $ArtifactDirectory"
Write-Host 'Sequential full compile/map/physical-route/audit/STA/bitstream flow; live output follows.'
$runnerArguments = @('-u', $runner, '--run', $ArtifactDirectory)
if ($ResumeCompiled) { $runnerArguments += '--resume-compiled' }
if ($ResumeRouted) { $runnerArguments += '--resume-routed' }
if ($ResumeSta) { $runnerArguments += '--resume-sta' }
& $python @runnerArguments 2>&1 | Tee-Object -FilePath (Join-Path $ArtifactDirectory 'live_tee.log') -Append
$flowExitCode = $LASTEXITCODE
Write-Host "RUNNER_EXIT_CODE: $flowExitCode"
exit $flowExitCode
