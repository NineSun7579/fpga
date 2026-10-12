param([string]$Out)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
$taTask=Get-Process ta
$taRoot=[System.Windows.Automation.AutomationElement]::FromHandle($taTask.MainWindowHandle)
$taEdits=$taRoot.FindAll([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)))
if($taEdits.Count -ne 3){throw 'Expected import dialog with three fields'}
$taBase=(Resolve-Path 'project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01').Path.Replace('\','/')
$taDB="$taBase/$Out/synthesis.adf"
if(-not (Test-Path $taDB)){$taDB="$taBase/A_original_inputs/synthesis.adf"}
$taSDC="$taBase/$Out/combined.sdc"
if(-not (Test-Path $taSDC)){$taSDC="$taBase/$Out/combined.fdc"}
$taValues=@($taDB,$taSDC,"$taBase/$Out")
for($taIdx=0;$taIdx -lt 3;$taIdx++){ $taEdits[$taIdx].GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($taValues[$taIdx]) }
$taButton=$taRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Finish')))
$taButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
$taValues | ConvertTo-Json | Set-Content "$taBase/$Out/ui_import.json"
