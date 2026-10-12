$ErrorActionPreference='Stop'
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class TAActivate { [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd,IntPtr process); [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId(); [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a,uint b,bool attach); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd,int cmd); }'
$taHandle=(Get-Process ta).MainWindowHandle
$thisThread=[TAActivate]::GetCurrentThreadId()
$foregroundThread=[TAActivate]::GetWindowThreadProcessId([TAActivate]::GetForegroundWindow(),[IntPtr]::Zero)
$targetThread=[TAActivate]::GetWindowThreadProcessId($taHandle,[IntPtr]::Zero)
[TAActivate]::AttachThreadInput($thisThread,$foregroundThread,$true) | Out-Null
[TAActivate]::AttachThreadInput($thisThread,$targetThread,$true) | Out-Null
[TAActivate]::ShowWindow($taHandle,9) | Out-Null
[TAActivate]::SetForegroundWindow($taHandle)
[TAActivate]::AttachThreadInput($thisThread,$targetThread,$false) | Out-Null
[TAActivate]::AttachThreadInput($thisThread,$foregroundThread,$false) | Out-Null
