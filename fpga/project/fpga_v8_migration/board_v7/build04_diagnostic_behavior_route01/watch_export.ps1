$Host.UI.RawUI.WindowTitle = 'build04 official functional netlist / routed graph - live log'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
while ($true) {
 foreach ($stage in @('functional','graph')) {
  $path=Join-Path $root ($stage+'.log')
  if(Test-Path $path) { Write-Host ('--- '+$stage+' '+(Get-Date)); Get-Content $path -Tail 20 | Write-Host }
 }
 if(Test-Path (Join-Path $root 'export_result.json')) {Write-Host 'Official export receipts saved'; Read-Host 'Press Enter to close';break}
 Start-Sleep -Seconds 5
 Clear-Host
}
