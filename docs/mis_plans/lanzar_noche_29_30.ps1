# Lanzador nocturno: tanda 29 y luego tanda 30, en serie, en la misma carpeta.
# Uso (desde la raiz del repo):
#   powershell -ExecutionPolicy Bypass -File docs\mis_plans\lanzar_noche_29_30.ps1            -> arranca a las 22:00
#   powershell -ExecutionPolicy Bypass -File docs\mis_plans\lanzar_noche_29_30.ps1 -Hora ahora
#   powershell -ExecutionPolicy Bypass -File docs\mis_plans\lanzar_noche_29_30.ps1 -Hora 23:30
# Cada tanda la corre tools\tandas\lanzar_prompt.ps1, que relanza la sesion al restablecerse el
# limite de uso y termina cuando existe docs\informes\<tanda>\CERRADO.txt. Si la 29 cierra con
# BLOQUEADO, la 30 no se lanza.
param([string]$Hora = '22:00')

$repo = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repo
$lanzador = Join-Path $repo 'tools\tandas\lanzar_prompt.ps1'
$logDir = Join-Path $repo 'docs\informes\noche_29_30'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'noche.log'
function Log($t) { $l = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t; Write-Host $l; Add-Content -Path $log -Value $l -Encoding UTF8 }

if ($Hora -ne 'ahora') {
  $inicio = [datetime]::ParseExact($Hora, 'HH:mm', $null)
  if ($inicio -lt (Get-Date)) { $inicio = $inicio.AddDays(1) }
  Log "Esperando hasta $inicio para lanzar la tanda 29."
  while ((Get-Date) -lt $inicio) { Start-Sleep -Seconds 60 }
}

foreach ($t in @('tanda29', 'tanda30')) {
  $cierre = Join-Path $repo "docs\informes\$t\CERRADO.txt"
  if (Test-Path $cierre) {
    Log "$t ya tiene CERRADO.txt; no se relanza: $((Get-Content $cierre -TotalCount 1))"
  } else {
    Log "Lanzando $t."
    & powershell -ExecutionPolicy Bypass -File $lanzador -Nombre $t
    Log "$t termino (codigo $LASTEXITCODE)."
  }
  if (-not (Test-Path $cierre)) { Log "$t sin CERRADO.txt. Se detiene la noche."; exit 1 }
  $primera = Get-Content $cierre -TotalCount 1
  Log "${t}: $primera"
  if ($primera -like 'BLOQUEADO*') { Log 'Bloqueada: no se sigue con la siguiente tanda.'; exit 2 }
}
Log 'Noche terminada: tandas 29 y 30 cerradas.'
