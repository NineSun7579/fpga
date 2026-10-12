param([switch]$Open,[switch]$Targets,[switch]$Report)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
$taTask=Get-Process ta
$condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$taTask.Id)
function FindDialog {
 $windows=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$condition)
 foreach($window in $windows){
  if($window.Current.ClassName -eq 'fabric_space::taTimingSettingDialog'){return $window}
  $found=$window.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'fabric_space::taTimingSettingDialog')))
  if($found){return $found}
 }
}
if($Open){
 $root=[System.Windows.Automation.AutomationElement]::FromHandle($taTask.MainWindowHandle)
 $button=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Report Timing')))
 $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
}
$dlg=FindDialog
if(-not $dlg){throw 'Settings dialog is not open'}
$items=$dlg.FindAll([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::DataItem)))
if($items.Count -ge 12){$items[11].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()}
if($Targets){
 $tab=$dlg.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Targets')))
 $tab.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
}
$dlg.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition) | ForEach-Object {
 $vp=$null;$value='';if($_.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){$value=$vp.Current.Value}
 '{0}|{1}|{2}|{3}' -f $_.Current.Name,$_.Current.ClassName,$_.Current.ControlType.ProgrammaticName,$value
}
if($Report){
 $button=$dlg.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Report')))
 $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
}
