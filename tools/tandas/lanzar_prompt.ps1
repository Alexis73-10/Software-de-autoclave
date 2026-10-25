# lanzar_prompt.ps1 - Ejecuta un prompt de Claude Code sin supervision. Si se agota el limite de uso,
# lee del mensaje la hora en que se restablece, espera hasta esa hora y relanza solo.
# Lo ejecuta CRISTIAN (no Claude Code), desde la raiz del repo, en UNA sola ventana:
#   powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_prompt.ps1 -Nombre versionado
# Convenciones (las fija la instruccion de cada trabajo):
#   prompt : docs\mis_plans\prompt_claude_code_<Nombre>.md
#   cierre : docs\informes\<Nombre>\CERRADO.txt  (Claude Code lo escribe como ultimo paso)
#   log    : docs\informes\<Nombre>\lanzador.log y sesion_NN_*.log
# Opcionales:
#   -HoraLimite "2026-10-27 08:00"  deja de esperar/relanzar a esa hora (defecto: 7 dias, cubre el limite semanal)
#   -MaxSinAvance 3                 sesiones seguidas que terminan SIN limite de uso y SIN cierre antes de rendirse
#   -MargenMin 3                    minutos extra despues de la hora de restablecimiento
#   -ProbarTexto <archivo>          solo prueba el analisis del mensaje de limite y sale (no lanza nada)

param(
  [string]$Nombre = '',
  [string]$HoraLimite = '',
  [int]$MaxSinAvance = 3,
  [int]$MargenMin = 3,
  [string]$ProbarTexto = ''
)

$ErrorActionPreference = 'Continue'

# --- Analisis del mensaje de limite -------------------------------------------------------------
# Formatos conocidos del CLI:
#   "Claude AI usage limit reached|1761400800"            (epoch Unix, versiones antiguas)
#   "5-hour limit reached - resets 3am (America/Bogota)"  (hora suelta)
#   "Your limit will reset at 3:30pm"                     (hora con minutos)
#   "Weekly limit reached - resets Sat 10am" / "resets Oct 31, 10am"  (con dia o fecha)
# Solo se mira el final de la salida (ultimas 40 lineas) y se exige la palabra "limit" ahi, para no
# confundir con texto que Claude Code haya escrito o leido durante la sesion.
function Leer-Restablecimiento([string]$texto, [datetime]$ahora) {
  if (-not $texto) { return $null }
  $lineas = $texto -split "`r?`n"
  $cola = ($lineas | Select-Object -Last 40) -join "`n"
  if ($cola -notmatch '(?i)limit') { return $null }

  if ($cola -match '(?i)limit reached\|(\d{10})') {
    return [DateTimeOffset]::FromUnixTimeSeconds([int64]$Matches[1]).LocalDateTime
  }

  $patron = '(?i)resets?\s+(?:at\s+)?' +
            '(?:(?<dia>mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?' +
            '(?:(?<mes>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?<d>\d{1,2}),?\s+)?' +
            '(?:at\s+)?(?<h>\d{1,2})(?::(?<m>\d{2}))?\s*(?<ap>[ap])\.?m'
  $todas = [regex]::Matches($cola, $patron)
  if ($todas.Count -eq 0) { return $null }
  $g = $todas[$todas.Count - 1].Groups            # la ultima aparicion es la del mensaje final

  $h = [int]$g['h'].Value; $m = if ($g['m'].Success) { [int]$g['m'].Value } else { 0 }
  if ($h -lt 1 -or $h -gt 12 -or $m -gt 59) { return $null }
  if ($g['ap'].Value -ieq 'p' -and $h -ne 12) { $h += 12 }
  if ($g['ap'].Value -ieq 'a' -and $h -eq 12) { $h = 0 }

  if ($g['mes'].Success) {                         # fecha explicita: "Oct 31, 10am"
    $meses = 'jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'
    $mes = [array]::IndexOf($meses, $g['mes'].Value.Substring(0,3).ToLower()) + 1
    $anio = $ahora.Year
    try { $t = Get-Date -Year $anio -Month $mes -Day ([int]$g['d'].Value) -Hour $h -Minute $m -Second 0 -Millisecond 0 } catch { return $null }
    if ($t -lt $ahora.AddDays(-1)) { $t = $t.AddYears(1) }   # "Jan 2" leido en diciembre
    return $t
  }

  $t = $ahora.Date.AddHours($h).AddMinutes($m)
  if ($g['dia'].Success) {                         # dia de la semana: "Sat 10am"
    $dias = 'sun','mon','tue','wed','thu','fri','sat'
    $objetivo = [array]::IndexOf($dias, $g['dia'].Value.Substring(0,3).ToLower())
    $delta = ($objetivo - [int]$ahora.DayOfWeek + 7) % 7
    $t = $t.AddDays($delta)
    if ($t -le $ahora) { $t = $t.AddDays(7) }
  } elseif ($t -le $ahora) {
    $t = $t.AddDays(1)                             # hora suelta ya pasada hoy -> manana
  }
  return $t
}

if ($ProbarTexto) {
  $r = Leer-Restablecimiento (Get-Content $ProbarTexto -Raw) (Get-Date)
  if ($r) { "Restablece: {0:yyyy-MM-dd HH:mm}" -f $r } else { 'Sin mensaje de limite reconocible' }
  exit 0
}

# --- Preparacion --------------------------------------------------------------------------------
if (-not $Nombre) { Write-Host 'Falta -Nombre (p. ej. -Nombre versionado).'; exit 1 }
$repo = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repo
$logDir = Join-Path $repo "docs\informes\$Nombre"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'lanzador.log'
function Log($t) { $l = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t; Write-Host $l; Add-Content -Path $log -Value $l -Encoding UTF8 }

$mutex = New-Object System.Threading.Mutex($false, "Global\EspecifikaPrompt_$Nombre")
if (-not $mutex.WaitOne(0)) { Log 'Ya hay otro lanzador de este trabajo abierto. Este se cierra.'; exit 2 }

# Mantiene el PC despierto mientras espera o trabaja (cerrar la tapa igual lo suspende).
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[Win32.Power]::SetThreadExecutionState([uint32]'0x80000001') | Out-Null

function Terminar([int]$codigo) {
  [Win32.Power]::SetThreadExecutionState([uint32]'0x80000000') | Out-Null
  $mutex.ReleaseMutex(); exit $codigo
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Log 'ERROR: no se encuentra "claude" (CLI de Claude Code).'; Terminar 1 }
$prompt = "docs\mis_plans\prompt_claude_code_$Nombre.md"
if (-not (Test-Path $prompt)) { Log "ERROR: no existe $prompt."; Terminar 1 }
$cierre = Join-Path $logDir 'CERRADO.txt'
$limite = if ($HoraLimite) { [datetime]::Parse($HoraLimite) } else { (Get-Date).AddDays(7) }
Log ("Inicio '{0}'. claude: {1}. Limite del lanzador: {2:yyyy-MM-dd HH:mm}" -f $Nombre, (claude --version 2>&1), $limite)

# Espera en tramos de 5 min (Ctrl+C responde y el log muestra que sigue vivo).
function Esperar-Hasta([datetime]$t) {
  while ((Get-Date) -lt $t) {
    if ((Get-Date) -ge $limite) { return $false }
    $falta = $t - (Get-Date)
    Log ("Esperando restablecimiento: faltan {0:hh\:mm} (hasta {1:yyyy-MM-dd HH:mm})." -f $falta, $t)
    Start-Sleep -Seconds ([math]::Min(300, [math]::Max(1, [int]$falta.TotalSeconds)))
  }
  return $true
}

$texto = "Lee completo docs/mis_plans/prompt_claude_code_$Nombre.md y ejecutalo al pie de la letra. " +
         "Si ya hay trabajo hecho (rama, commits o docs/informes/$Nombre/estado.md), reanuda desde el primer paso sin terminar."
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'   # sin esto -p mata los subagentes 10 min despues del ultimo turno

# --- Bucle principal ----------------------------------------------------------------------------
$i = 0; $sinAvance = 0
while (-not (Test-Path $cierre)) {
  if ((Get-Date) -ge $limite) { Log 'Limite del lanzador alcanzado sin cierre. Fin.'; Terminar 3 }
  $i++
  $salida = Join-Path $logDir ("sesion_{0:00}_{1:yyyyMMdd_HHmm}.log" -f $i, (Get-Date))
  Log "Intento $i. Salida: $salida"
  & claude -p $texto --dangerously-skip-permissions *>> $salida
  Log "La sesion termino (codigo $LASTEXITCODE)."
  if (Test-Path $cierre) { break }

  $msg = Get-Content $salida -Raw -ErrorAction SilentlyContinue
  $reset = Leer-Restablecimiento $msg (Get-Date)
  if ($reset) {
    $sinAvance = 0
    $hasta = $reset.AddMinutes($MargenMin)
    Log ("Limite de uso detectado: se restablece {0:yyyy-MM-dd HH:mm}. Relanzo a las {1:HH:mm}." -f $reset, $hasta)
    if (-not (Esperar-Hasta $hasta)) { Log 'El restablecimiento cae despues del limite del lanzador. Fin.'; Terminar 3 }
  } elseif ($msg -match '(?i)usage limit|limit reached|rate limit') {
    $sinAvance = 0
    Log 'Limite de uso detectado sin hora legible. Reintento en 15 min.'
    Start-Sleep -Seconds 900
  } else {
    $sinAvance++
    Log "Termino sin cierre y sin limite de uso ($sinAvance de $MaxSinAvance). Revisar $salida."
    if ($sinAvance -ge $MaxSinAvance) { Log 'Demasiadas sesiones sin avance. Me detengo para no gastar uso.'; Terminar 4 }
    Start-Sleep -Seconds 120
  }
}
Log "Trabajo '$Nombre' cerrado: $(Get-Content $cierre -Raw)"
Terminar 0
