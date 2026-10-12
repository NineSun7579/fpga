param([string]$Script)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName System.Windows.Forms
$taTask=Get-Process ta
$taRoot=[System.Windows.Automation.AutomationElement]::FromHandle($taTask.MainWindowHandle)
$taEditor=$taRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'TclTextEdit')))
$taEditor.SetFocus()
$taScriptPath=(Resolve-Path $Script).Path.Replace('\','/')
$taCommand="source {$taScriptPath}"
$taKeys=-join ($taCommand.ToCharArray() | ForEach-Object {if($_ -eq '{'){'{{}'}elseif($_ -eq '}'){'{}}'}elseif($_ -eq '+'){'{+}'}elseif($_ -eq '%'){'{%}'}elseif($_ -eq '^'){'{^}'}elseif($_ -eq '('){'{(}'}elseif($_ -eq ')'){'{)}'}else{[string]$_}})
[System.Windows.Forms.SendKeys]::SendWait($taKeys)
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
Write-Output "TA console source {$taScriptPath}"
