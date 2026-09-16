# GenAI Inventory Assistant - Startup Script
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Starting GenAI Inventory & Demand-Forecasting Assistant" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Launch FastAPI Backend on port 8000
Write-Host "`n[1/2] Launching FastAPI Backend (port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- FastAPI Backend ---' -ForegroundColor Green; python -m uvicorn src.api.main:app --reload --port 8000"

# 2. Launch Vite Frontend on port 5173
Write-Host "[2/2] Launching React Vite Frontend (port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- React Frontend ---' -ForegroundColor Cyan; cd frontend; npm run dev"

Write-Host "`nServices started successfully!" -ForegroundColor Green
Write-Host "• Frontend UI: http://localhost:5173" -ForegroundColor White
Write-Host "• Backend API & Swagger Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "• ChromaDB Vector Store: data/vector_store/chroma" -ForegroundColor White
