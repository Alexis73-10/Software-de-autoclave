# lanzar_tanda.ps1 — Ejecuta una tanda de Claude Code sin supervision y la relanza si se corta.
# Lo ejecuta CRISTIAN (no Claude Code), desde la raiz del repo:
#   powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_tanda.ps1 -Tanda 8
# Opcionales:
#   -EsperarIndice <ruta>   espera a que exista ese archivo antes de arrancar (encadenar tras otra tanda)
#   -CerrarVSCode           cierra VS Code al arrancar (solo si se espero a otra tanda y esta cerro)
#   -HoraLimite "2026-10-23 14:00"   deja de relanzar a esa hora (defecto: 36 h desde el inicio)
# Abrir UNA sola ventana con este script. Log: docs\informes\tanda<N>\lanzador.log

param(
  [Parameter(Mandatory = $true)][int]$Tanda,
  [string]$EsperarIndice = '',
  [switch]$CerrarVSCode,
  [string]$HoraLimite = ''
)

$ErrorActionPreference = 'Continue'
$repo   = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repo
$logDir = Join-Path $repo "docs\informes\tanda$Tanda"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log    = Join-Path $logDir 'lanzador.log'
function Log($m) { $l = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $m; Write-Host $l; Add-Content -Path $log -Value $l -Encoding UTF8 }

# Una sola instancia por tanda (evita dos sesiones sobre la misma carpeta).
$mutex = New-Object System.Threading.Mutex($false, "Global\EspecifikaTanda$Tanda")
if (-not $mutex.WaitOne(0)) { Log 'Ya hay otro lanzador de esta tanda abierto. Este se cierra.'; exit 2 }

# Mantener el PC despierto mientras corre (no cambia el plan de energia; cerrar la tapa igual lo suspende).
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[Win32.Power]::SetThreadExecutionState([uint32]'0x80000001') | Out-Null

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Log 'ERROR: no se encuentra "claude" (CLI de Claude Code). Abortado.'; exit 1 }
$prompt = "docs\mis_plans\prompt_claude_code_tanda_$Tanda.md"
if (-not (Test-Path $prompt)) { Log "ERROR: no existe $prompt. Abortado."; exit 1 }
$limite = if ($HoraLimite) { [datetime]::Parse($HoraLimite) } else { (Get-Date).AddHours(36) }
Log ("Inicio tanda {0}. claude: {1}. Limite: {2:yyyy-MM-dd HH:mm}" -f $Tanda, (claude --version 2>&1), $limite)

$estado = Join-Path $logDir 'estado.md'
function TandaCerrada { (Test-Path $estado) -and (Select-String -Path $estado -Pattern '^\|\s*Z\s*\|\s*Hecha' -Quiet) }

if ($EsperarIndice) {
  while (-not (Test-Path $EsperarIndice)) {
    if ((Get-Date) -ge $limite) { Log 'Limite alcanzado esperando la tanda anterior. Fin.'; exit 3 }
    Log "Esperando $EsperarIndice. Reviso en 5 min."; Start-Sleep -Seconds 300
  }
  if ($CerrarVSCode) {
    Log 'Tanda anterior cerrada. 5 min de gracia y cierro VS Code.'; Start-Sleep -Seconds 300
    $vsc = Get-Process -Name 'Code' -ErrorAction SilentlyContinue
    if ($vsc) { $vsc | ForEach-Object { $null = $_.CloseMainWindow() }; Start-Sleep -Seconds 30
      $v = Get-Process -Name 'Code' -ErrorAction SilentlyContinue; if ($v) { $v | Stop-Process -Force; Log 'VS Code forzado.' } else { Log 'VS Code cerrado.' } }
  }
}

$texto = "Lee completo docs/mis_plans/prompt_claude_code_tanda_$Tanda.md y ejecutalo al pie de la letra. Si existe docs/informes/tanda$Tanda/estado.md, reanuda desde la primera etapa sin terminar."
# Sin esto, en modo -p el CLI mata los subagentes en segundo plano 10 min despues del ultimo turno.
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$i = 0
while (-not (TandaCerrada)) {
  if ((Get-Date) -ge $limite) { Log 'Limite alcanzado sin cierre. Fin del lanzador.'; break }
  $i++
  $salida = Join-Path $logDir ("sesion_{0:00}_{1:yyyyMMdd_HHmm}.log" -f $i, (Get-Date))
  Log "Intento $i. Salida: $salida"
  & claude -p $texto --dangerously-skip-permissions *>> $salida
  Log "La sesion termino (codigo $LASTEXITCODE)."
  if (TandaCerrada) { break }
  $msg = (Get-Content $salida -Raw -ErrorAction SilentlyContinue)
  if ($msg -match 'resets\s+([0-9]{1,2}(:[0-9]{2})?\s*[ap]m)') { Log "Limite de uso: se restablece a las $($Matches[1]). Reintento cada 10 min." }
  Start-Sleep -Seconds 600
}
if (TandaCerrada) { Log "Tanda $Tanda cerrada. Ver docs\informes\tanda$Tanda\estado.md y el indice." }
[Win32.Power]::SetThreadExecutionState([uint32]'0x80000000') | Out-Null
$mutex.ReleaseMutex()
