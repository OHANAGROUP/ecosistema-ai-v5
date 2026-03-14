<#
.SYNOPSIS
    Espera hasta una hora específica para reinicio de cuota y ejecuta Claude Code con contexto.

.PARAMETER HoraObjetivo
    Hora en formato "HH:mm" (ej. "22:00").

.PARAMETER DirectorioTrabajo
    Ruta del proyecto donde ejecutar Claude.

.PARAMETER Comando
    Comando directo para Claude (ej. "continúa con el refactor").

.PARAMETER ArchivoInstrucciones
    Ruta a un archivo .txt o .md con las instrucciones detalladas.

.EXAMPLE
    .\esperar_y_ejecutar_claude.ps1 -HoraObjetivo "22:00" -ArchivoInstrucciones "continuar_refactor.md"
#>

param(
    [string]$HoraObjetivo = "22:00",
    [string]$DirectorioTrabajo = (Get-Location).Path,
    [string]$Comando = "",
    [string]$ArchivoInstrucciones = "continuar_refactor.md"
)

# Configuración Visual
$Host.UI.RawUI.WindowTitle = "Claude Resume Utility - Waiting for $HoraObjetivo"
$accent = "#7c3aed" # Violeta Obsidian

# 1. Validaciones de Pre-vuelo
if (-not (Test-Path $DirectorioTrabajo)) {
    Write-Host "[ERROR] El directorio '$DirectorioTrabajo' no existe." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Claude Code ('claude') no está instalado o no está en el PATH." -ForegroundColor Red
    exit 1
}

try {
    $targetTime = [DateTime]::ParseExact($HoraObjetivo, "HH:mm", $null)
    if ((Get-Date) -gt $targetTime) { $targetTime = $targetTime.AddDays(1) }
} catch {
    Write-Host "[ERROR] Formato de hora inválido. Use HH:mm (ej. 22:00)." -ForegroundColor Red
    exit 1
}

# 2. Resumen de Operación
Write-Host "`n[CLAUDE CODE RESUME UTILITY]" -ForegroundColor Cyan
Write-Host "------------------------------------------------"
Write-Host "Directorio: $DirectorioTrabajo" -ForegroundColor Gray
Write-Host "Objetivo:   $($targetTime.ToString('HH:mm:ss')) (Limit Reset)" -ForegroundColor Magenta

if ($ArchivoInstrucciones) {
    if (Test-Path (Join-Path $DirectorioTrabajo $ArchivoInstrucciones)) {
        Write-Host "Contexto:   Usando archivo '$ArchivoInstrucciones'" -ForegroundColor Green
    } else {
        Write-Host "Contexto:   Sin instrucciones externas (archivo no encontrado)" -ForegroundColor Yellow
    }
}
Write-Host "------------------------------------------------`n"

# 3. Espera Activa con Write-Progress (Nativo y Robusto)
$startTime = Get-Date
while ((Get-Date) -lt $targetTime) {
    $now = Get-Date
    $remaining = $targetTime - $now
    $totalSecs = ($targetTime - $startTime).TotalSeconds
    $elapsedSecs = ($now - $startTime).TotalSeconds
    $percent = [Math]::Min(100, ($elapsedSecs / $totalSecs) * 100)
    
    $statusMsg = "Reinicio en $($remaining.ToString('hh\:mm\:ss')) | $($percent.ToString('0.0'))%"
    
    Write-Progress -Activity "Claude Code: Esperando Reset de Cuota" `
                   -Status $statusMsg `
                   -PercentComplete $percent
    
    # Actualización en consola cada minuto para no saturar procesos, pero el progress bar es suave
    if ($now.Second % 60 -eq 0) {
        Write-Host ("[" + (Get-Date -Format "HH:mm") + "] Sincronizado... Faltan " + $remaining.ToString('hh\:mm\:ss')) -ForegroundColor Gray
    }
    
    Start-Sleep -Seconds 1
}

Write-Progress -Activity "Claude Code" -Completed

# 4. Ejecución y Notificación
Write-Host "`n`n[!] TIEMPO CUMPLIDO - REINICIANDO PROCESO" -ForegroundColor Green -BackgroundColor Black
Set-Location $DirectorioTrabajo

# Log de ejecución para Antigravity
$logFile = Join-Path $DirectorioTrabajo "claude_resume.log"
"Resumed at: $(Get-Date) | Target: $HoraObjetivo" | Out-File $logFile -Append

if ($ArchivoInstrucciones -and (Test-Path (Join-Path $DirectorioTrabajo $ArchivoInstrucciones))) {
    Write-Host "Cargando instrucciones de '$ArchivoInstrucciones'..." -ForegroundColor Cyan
    $prompt = Get-Content (Join-Path $DirectorioTrabajo $ArchivoInstrucciones) -Raw
    # Ejecutamos claude enviando el prompt inicial
    claude "$prompt"
} elseif ($Comando) {
    claude "$Comando"
} else {
    claude
}
