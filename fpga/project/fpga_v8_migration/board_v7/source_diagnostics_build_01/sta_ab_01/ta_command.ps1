param([Parameter(Mandatory=$true)][string]$Command)
$ErrorActionPreference='Stop'
& "$PSScriptRoot/ta_activate.ps1" | Out-Null
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class TAConsoleNative { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }'
[TAConsoleNative]::SetForegroundWindow((Get-Process ta).MainWindowHandle) | Out-Null
$taRoot=[System.Windows.Automation.AutomationElement]::FromHandle((Get-Process ta).MainWindowHandle)
$taEditor=$taRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'TclTextEdit')))
if(-not $taEditor){throw 'TA console is not available'}
$taEditor.SetFocus()
Start-Sleep -Milliseconds 300
Set-Clipboard -Value $Command
[System.Windows.Forms.SendKeys]::SendWait('^a')
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
Write-Output $Command
