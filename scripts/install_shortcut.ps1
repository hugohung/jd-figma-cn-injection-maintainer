$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$launchScript = Join-Path $root "launch_figma_cn.py"
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
$launcher = if ($pythonw) { $pythonw } else { $python }
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$shortcutPaths = @(
  (Join-Path $desktop "Figma CN.lnk"),
  (Join-Path $programs "Figma CN.lnk")
)
$figmaIcon = Join-Path $env:LOCALAPPDATA "Figma\Figma.exe"

if (-not $launcher) {
  throw "Python was not found."
}

foreach ($shortcutPath in $shortcutPaths) {
  $parent = Split-Path -Parent $shortcutPath
  New-Item -ItemType Directory -Force -Path $parent | Out-Null

  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($shortcutPath)
  $shortcut.TargetPath = $launcher
  $shortcut.Arguments = "`"$launchScript`""
  $shortcut.WorkingDirectory = $root
  if (Test-Path $figmaIcon) {
    $shortcut.IconLocation = $figmaIcon
  }
  $shortcut.Description = "Start Figma and inject the Chinese UI helper"
  $shortcut.Save()
  Write-Host "Created shortcut: $shortcutPath"
}
