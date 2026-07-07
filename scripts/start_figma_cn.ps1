$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
$launcher = if ($pythonw) { $pythonw } else { $python }

if (-not $launcher) {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show("Python was not found. Cannot start Figma CN.", "Figma CN")
  exit 1
}

Start-Process -FilePath $launcher -ArgumentList @("`"$root\launch_figma_cn.py`"") -WorkingDirectory $root -WindowStyle Hidden
