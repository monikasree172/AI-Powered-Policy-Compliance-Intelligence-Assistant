Write-Host "Starting all ComplianceAI microservices..." -ForegroundColor Green

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\monik\Downloads\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\pca; python -m uvicorn services.retrieval.main:app --port 8001"
Start-Sleep 3

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\monik\Downloads\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\pca; python -m uvicorn services.interpretation.main:app --port 8002"
Start-Sleep 2

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\monik\Downloads\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\pca; python -m uvicorn services.compliance.main:app --port 8003"
Start-Sleep 2

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\monik\Downloads\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\pca; python -m uvicorn services.risk.main:app --port 8004"
Start-Sleep 2

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\monik\Downloads\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\pca; python -m uvicorn services.recommendation.main:app --port 8005"
Start-Sleep 2

Write-Host "Waiting for services to initialize..." -ForegroundColor Yellow
Start-Sleep 10

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\monik\Downloads\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\AI-Powered-Policy-Compliance-Intelligence-Assistant-main\pca; python -m uvicorn services.gateway.main:app --port 8000"
Start-Sleep 5

Write-Host "All 6 services started!" -ForegroundColor Green
Write-Host "Gateway:        http://localhost:8000" -ForegroundColor Cyan
Write-Host "Retrieval:      http://localhost:8001" -ForegroundColor Cyan
Write-Host "Interpretation: http://localhost:8002" -ForegroundColor Cyan
Write-Host "Compliance:     http://localhost:8003" -ForegroundColor Cyan
Write-Host "Risk:           http://localhost:8004" -ForegroundColor Cyan
Write-Host "Recommendation: http://localhost:8005" -ForegroundColor Cyan
Write-Host "Health check:   http://localhost:8000/api/v1/health" -ForegroundColor Cyan
