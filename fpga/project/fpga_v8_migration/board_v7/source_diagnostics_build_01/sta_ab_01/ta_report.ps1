$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
$taRoot=[System.Windows.Automation.AutomationElement]::FromHandle((Get-Process ta).MainWindowHandle)
$taButton=$taRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Report Timing')))
$taButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
