# GenAI Inventory & Demand-Forecasting Assistant

A full-stack AI-powered inventory management system that pairs statistical demand forecasting (Prophet/ARIMA-SARIMA) with a GenAI reasoning layer to provide explainable recommendations for supply-chain managers.

## Features

- **Explainable Forecasting**: Demand forecasts with plain-language explanations
- **RAG-Powered Context**: Automatic retrieval of promotions, festivals, market events
- **Natural Language Chat**: Ask questions, explore what-if scenarios
- **Human-in-the-Loop**: All AI recommendations require human approval
- **Anomaly Detection**: Automatic investigation of forecast deviations

## Tech Stack

- **Backend**: FastAPI + Python 3.12
- **Frontend**: React + Vite + TypeScript + Tailwind CSS + shadcn/ui
- **Forecasting**: Prophet + SARIMA (statsmodels)
- **GenAI**: OpenRouter (free open-weight LLMs)
- **RAG**: LangChain + sentence-transformers + FAISS
- **Database**: SQLite (structured) + FAISS (vectors)

## Quick Start

```bash
# Backend
pip install -r requirements.txt
python -m src.ingestion.load
uvicorn src.api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

## License

MIT
