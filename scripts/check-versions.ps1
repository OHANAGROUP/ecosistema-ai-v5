# check-versions.ps1 - ALPA SaaS Version Guard
# Ejecutar antes de cada despliegue a produccion para evitar mix de versiones cacheadas
$badPatterns = @("v4\.0\.0", "v4\.1\.0", "3\.1\.10\.", "Versié")
$files = Get-ChildItem -Path "frontend" -Recurse -Include "*.html", "*.js" | Where-Object { $_.FullName -notmatch "node_modules|deploy|backup" }
$hits = $files | Select-String -Pattern ($badPatterns -join "|")

if ($hits) { 
    Write-Error "[ERROR] Versiones contaminadas detectadas anidadas en el codigo base:"
    $hits | Format-Table -AutoSize
    exit 1 
}
else { 
    Write-Host "[OK] Versiones limpias. Sistema listo para despliegue." -ForegroundColor Green
}
