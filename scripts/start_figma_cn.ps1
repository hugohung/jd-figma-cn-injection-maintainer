$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source

if (-not $python) {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show("Python was not found. Cannot start Figma CN.", "Figma CN")
  exit 1
}

Start-Process -FilePath $python -ArgumentList @("`"$root\launch_figma_cn.py`"") -WorkingDirectory $root -WindowStyle Hidden
