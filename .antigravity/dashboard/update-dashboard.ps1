param(
    [string]$ProjectRoot = (Get-Location),
    [switch]$OpenBrowser
)

$dashboardDir = Join-Path $ProjectRoot '.antigravity\dashboard'
if (-not (Test-Path $dashboardDir)) { 
    New-Item -ItemType Directory -Path $dashboardDir -Force | Out-Null 
}

$planPath = Join-Path $ProjectRoot 'implementation_plan.md'
$logPath = Join-Path $ProjectRoot 'logs\antigravity.log'

$tareas = @()
if (Test-Path $planPath) {
    Try {
        $content = Get-Content $planPath -ErrorAction SilentlyContinue
        foreach ($line in $content) {
            if ($line -match '- \[( |x|/)\] (.*)') {
                $done = $matches[1] -eq 'x'
                $texto = $matches[2]
                $tareas += @{ texto = $texto; done = $done }
            }
        }
    } Catch {}
} 

if ($tareas.Count -eq 0) {
    $tareas += @{ texto = 'Inicializar implementation_plan.md'; done = $false }
    $tareas += @{ texto = 'Configurar dashboard'; done = $true }
}

$gitLog = @()
Try {
    $gitOutput = git log -n 8 --pretty=format:'%h|%s|%cr' 2>$null
    foreach ($line in $gitOutput) {
        if ($line.Trim()) {
            $parts = $line.Split('|')
            if ($parts.Count -ge 3) {
                $gitLog += @{ hash = $parts[0]; msg = $parts[1]; time = $parts[2] }
            }
        }
    }
} Catch {}

$sessionLog = @()
if (Test-Path $logPath) {
    Try {
        $logContent = Get-Content $logPath -ErrorAction SilentlyContinue | Select-Object -Last 10
        foreach ($line in $logContent) {
            if ($line -match '\[(.*)\] \[(.*)\] (.*)') {
                $sessionLog += @{ ts = $matches[1]; level = $matches[2]; msg = $matches[3] }
            } else {
                $sessionLog += @{ ts = ''; level = 'INFO'; msg = $line }
            }
        }
    } Catch {}
}

if ($sessionLog.Count -eq 0) {
    $sessionLog += @{ ts = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'); level = 'INFO'; msg = 'Dashboard inicializado' }
}

$totalTareas = [math]::Max($tareas.Count, 10)
$hechas = ($tareas | Where-Object { $_.done }).Count

$proyectos = @(
    @{
        id = 1
        nombre = (Split-Path -Leaf $ProjectRoot)
        path = $ProjectRoot
        status = 'active'
        tareasTotal = $totalTareas
        tareasHechas = $hechas
        proximaReanudacion = $null
        tareas = $tareas
        gitLog = $gitLog
        sessionLog = $sessionLog
    }
)

$jsonData = $proyectos | ConvertTo-Json -Depth 10 -Compress
$dateStr = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$jsPrefix = 'window.ANTIGRAVITY_DATA = { proyectos: '
$jsSuffix = ", lastUpdate: '$dateStr' };"
$jsContent = $jsPrefix + $jsonData + $jsSuffix

$jsContent | Out-File -FilePath (Join-Path $dashboardDir 'data.js') -Encoding UTF8 -Force

Write-Host '✓ Dashboard data updated: .antigravity\dashboard\data.js' -ForegroundColor 'Green'
