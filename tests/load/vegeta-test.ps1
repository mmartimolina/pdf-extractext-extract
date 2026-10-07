$ErrorActionPreference = "Stop"

$report = "tests/load/vegeta-report.txt"

Write-Host "Ejecutando prueba de carga con Vegeta..."
Write-Host "Carga: 50 requests/s durante 30 segundos"

docker run --rm -i `
  --add-host=host.docker.internal:host-gateway `
  -v "${PWD}/tests:/tests:ro" `
  peterevans/vegeta sh -c `
  "vegeta attack -rate=50/s -duration=30 s -targets=/tests/load/vegeta-target.txt | vegeta report" |
  Tee-Object -FilePath $report

Write-Host ""
Write-Host "Reporte guardado en $report"