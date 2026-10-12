param([string]$Name='Import DB and SDC')
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class TAMouse { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y); [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint dx,uint dy,uint data,UIntPtr extra); }'
[TAMouse]::SetProcessDPIAware() | Out-Null
$task=Get-Process ta
[TAMouse]::SetForegroundWindow($task.MainWindowHandle) | Out-Null
$root=[System.Windows.Automation.AutomationElement]::FromHandle($task.MainWindowHandle)
$button=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$Name)))
if(-not $button){throw "Missing control: $Name"}
$rect=$button.Current.BoundingRectangle
[TAMouse]::SetCursorPos([int]($rect.X+$rect.Width/2),[int]($rect.Y+$rect.Height/2)) | Out-Null
[TAMouse]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
[TAMouse]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
Write-Output "$Name $rect"
