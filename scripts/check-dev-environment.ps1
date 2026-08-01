$ErrorActionPreference = 'Stop'

function Get-ToolVersion([string]$name, [string[]]$arguments) {
  $command = Get-Command $name -ErrorAction SilentlyContinue
  if (-not $command) { throw "未找到 $name。请先安装后重新运行本脚本。" }
  $version = & $command.Source @arguments
  Write-Host "$name: $version"
}

Get-ToolVersion 'node' @('--version')
Get-ToolVersion 'pnpm' @('--version')

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '..\package.json'))) {
  throw '请在 Codex Skill Toolbox 项目中运行本脚本。'
}

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '..\node_modules'))) {
  Write-Host '未发现 node_modules，请先运行 pnpm install。' -ForegroundColor Yellow
} else {
  Write-Host '开发环境检查完成。' -ForegroundColor Green
}
