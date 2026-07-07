$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startScript = Join-Path $root "start_figma_cn.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$shortcutPaths = @(
  (Join-Path $desktop "Figma CN.lnk"),
  (Join-Path $programs "Figma CN.lnk")
)
$figmaIcon = Join-Path $env:LOCALAPPDATA "Figma\Figma.exe"

foreach ($shortcutPath in $shortcutPaths) {
  $parent = Split-Path -Parent $shortcutPath
  New-Item -ItemType Directory -Force -Path $parent | Out-Null

  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($shortcutPath)
  $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
  $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`""
  $shortcut.WorkingDirectory = $root
  if (Test-Path $figmaIcon) {
    $shortcut.IconLocation = $figmaIcon
  }
  $shortcut.Description = "Start Figma and inject the Chinese UI helper"
  $shortcut.Save()
  Write-Host "Created shortcut: $shortcutPath"
}
