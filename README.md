# GenAI Inventory & Demand-Forecasting Assistant

A full-stack AI-powered inventory management and demand-forecasting system. The application pairs statistical demand forecasting (Facebook Prophet and SARIMA) with a GenAI reasoning layer to produce explainable replenishment and transfer recommendations for supply-chain managers.

The backend exposes a FastAPI REST API that reads from a local SQLite database, serves precomputed forecasts, computes safety stock, reorder points, EOQ, inter-warehouse transfer opportunities, what-if scenarios, and anomaly alerts, and answers natural-language questions through a tool-calling reasoning agent. The frontend is a React single-page application that renders dashboards, forecast charts, replenishment queues, transfer comparisons, what-if simulation, and an AI copilot chat interface.

---

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Dataset and Ingestion Statistics](#dataset-and-ingestion-statistics)
- [System Requirements](#system-requirements)
- [Getting Started](#getting-started)
- [Running the Application](#running-the-application)
- [Verifying the Installation](#verifying-the-installation)
- [Environment Variables](#environment-variables)
- [Re-running Data Ingestion](#re-running-data-ingestion)
- [Backend API Reference](#backend-api-reference)
- [Frontend Views and Features](#frontend-views-and-features)
- [OpenRouter Configuration](#openrouter-configuration)
- [Project Structure](#project-structure)
- [Development Commands](#development-commands)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Key Features

- **Explainable Forecasting**: Demand forecasts with plain-language explanations and confidence intervals.
- **Prophet and SARIMA Models**: Switch between Prophet (with Indian festival regressors), SARIMA, and exponential smoothing.
- **RAG-Powered Context**: Automatic retrieval of promotions, festival calendars, supplier disruptions, and policy documents from ChromaDB.
- **Natural Language Chat**: Ask questions about SKU status, demand trends, and what-if scenarios; the agent uses tool calling internally.
- **Replenishment Engine**: Dynamic safety stock, reorder point (ROP), economic order quantity (EOQ), and stockout-risk scoring.
- **Inter-Warehouse Transfer Optimization**: Compare surplus-to-deficit stock transfers against external supplier purchase orders by cost and lead time.
- **What-If Scenario Simulator**: Stress-test demand shocks, supplier delays, and promotional lifts.
- **Human-in-the-Loop Approvals**: Every AI recommendation requires explicit manager approval before execution.
- **Anomaly Detection**: Automatic investigation of forecast deviations with severity classification.
- **No External Database Required**: SQLite and ChromaDB run locally.

---

## Tech Stack

| Layer        | Technology                                                        |
|--------------|-------------------------------------------------------------------|
| Backend      | Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2       |
| Database     | SQLite (WAL mode) for structured data, ChromaDB for vector search |
| Forecasting  | Prophet 1.1.5, SARIMA / exponential smoothing via statsmodels     |
| GenAI        | OpenRouter-compatible client with free open-weight model chain    |
| RAG          | LangChain, ChromaDB, sentence-transformers (`all-MiniLM-L6-v2`)   |
| Frontend     | React 19, TypeScript, Vite 8, Recharts, Vanilla CSS               |

---

## Dataset and Ingestion Statistics

After ingestion, the SQLite database contains the following datasets:

| Entity                      | Count      | Details                                                    |
|-----------------------------|------------|------------------------------------------------------------|
| Sales History               | 91,250     | Daily sales across 50 SKUs and 5 warehouses (Jan-Dec 2024) |
| Inventory Levels            | 91,250     | On-hand, on-order, ROP, and stockout flags                |
| SKU Master                  | 50 SKUs    | Budget, Economy, Standard, Premium, and Luxury categories |
| Warehouses                  | 5 hubs     | Delhi, Mumbai, Chennai, Kolkata, Pune                     |
| Distance / Transfer Matrix  | 25 pairs   | 5x5 inter-warehouse distance and unit transfer cost       |
| Supplier Lead Times         | 211 records| SKU-to-supplier lead time mappings                         |
| ChromaDB Documents          | 89 docs    | Indian festival calendar and supply-chain disruption docs  |

The data is loaded from CSVs in `data/processed`, `data/metadata`, and `data/rag_sources`.

---

## System Requirements

### Common requirements

- Git
- A POSIX shell (macOS/Linux) or PowerShell/CMD (Windows)
- At least 4 GB of free disk space (the SQLite database is around 28 MB after ingestion; vector store size depends on document count)

### macOS and Linux

- Python 3.11 or newer
- Node.js 18 or newer and npm 9 or newer
- On Debian/Ubuntu, build tools for native Python packages: `build-essential`, `python3-dev`, plus C compiler and make.
- On macOS with Apple Silicon, the Python packages in this project rely on wheels available for `arm64`; using the official Python installer or `pyenv` is recommended.

### Windows

- Python 3.11 or newer (official installer from python.org)
- Node.js 18 or newer and npm 9 or newer
- Visual Studio Build Tools or Microsoft C++ build tools are required for compiling native dependencies such as Prophet, statsmodels, and sentence-transformers if wheels are not available for your Python version. If pip fails to build a native extension, install the Visual Studio Build Tools with the "Desktop development with C++" workload before reinstalling the dependency.

---

## Getting Started

The following instructions are written for all three major platforms. Replace `python` with `python3` on macOS and Linux if your default `python` points to Python 2.

### Step 1: Clone the repository

```bash
git clone https://github.com/your-org/genai-inventory-assistant.git
cd genai-inventory-assistant
```

### Step 2: Install Python dependencies

Create an isolated virtual environment and install the backend requirements.

**macOS and Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows Command Prompt**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The project also exposes a `pyproject.toml` with the same dependency list. You may install the project itself with `pip install -e .` instead of `requirements.txt` if you prefer editable installs.

### Step 3: Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 4: Configure environment variables

Copy the example environment file and fill in your OpenRouter API key if you want live LLM inference.

```bash
cp .env.example .env
```

Edit `.env` to update:

- `OPENROUTER_API_KEY`: Your OpenRouter API key. Leave as the placeholder to run in high-fidelity simulation mode.
- `OPENROUTER_MODEL`: Primary model to use when a key is present.
- `OPENROUTER_FALLBACK_MODELS`: Comma-separated fallback model IDs.
- `DATABASE_URL`, `VECTOR_DB_PATH`, and other paths use sensible project-relative defaults.

### Step 5: Ingest data

Load the SQLite database and RAG documents. This step is required unless a pre-built database already exists at `data/inventory.db`.

```bash
python -m src.ingestion.load
```

### Step 6: Build or rebuild the vector store

Index festival calendar and supply-chain knowledge documents into ChromaDB. Run this if you change, add, or remove documents in `data/rag_sources` or `data/promotions_context`.

```bash
python -m src.rag.ingest
```

### Step 7: Start the application

Start the backend and frontend as described in the [Running the Application](#running-the-application) section.

---

## Running the Application

### Option A: Windows one-click script (PowerShell only)

Windows users can run the bundled startup script, which opens two new PowerShell windows for the backend and frontend:

```powershell
.\start_dev.ps1
```

The script starts:

- FastAPI backend on `http://localhost:8000`
- React frontend on `http://localhost:5173`

### Option B: Manual startup (all platforms)

Open two terminal windows and run the following commands.

**Terminal 1: Backend**

```bash
# Activate the virtual environment first if it is not already active.
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
uvicorn src.api.main:app --reload --port 8000
```

**Terminal 2: Frontend**

```bash
cd frontend
npm run dev
```

Then open `http://localhost:5173` in a browser.

### Option C: Run the frontend only against an existing backend

The Vite dev server proxies `/api` and `/health` to `http://127.0.0.1:8000`. If your backend is already running, start the frontend with `cd frontend && npm run dev`.

### Production build (optional)

To create an optimized frontend bundle:

```bash
cd frontend
npm run build
npm run preview
```

---

## Verifying the Installation

Once both servers are running, verify them with curl or a browser.

**Backend health check**

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","version":"1.0.0","timestamp":"2026-09-22T..."}
```

**API root**

```bash
curl http://localhost:8000/
```

**Frontend**

Open `http://localhost:5173`. The application loads the dashboard by default and shows replenishment alerts, active SKU count, warehouse status, and pending approval count.

**Sample API calls**

```bash
curl http://localhost:8000/api/skus?limit=5
curl http://localhost:8000/api/warehouses
curl "http://localhost:8000/api/replenishment/alerts?limit=10"
curl "http://localhost:8000/api/dashboard"
curl "http://localhost:8000/api/rag/search?query=festival+demand&limit=3"
```

---

## Environment Variables

The backend reads variables from a `.env` file at the project root or from the operating-system environment. The default values in this table are what the application uses when `.env` is absent or empty.

| Variable                          | Default                                            | Description                                          |
|-----------------------------------|----------------------------------------------------|------------------------------------------------------|
| `DATABASE_URL`                    | `sqlite:///data/inventory.db`                      | SQLite connection string                             |
| `OPENROUTER_API_KEY`              | empty string                                       | OpenRouter API key for live LLM calls                |
| `OPENROUTER_MODEL`                | `meta-llama/llama-3.3-70b-instruct:free`           | Primary OpenRouter model                             |
| `OPENROUTER_FALLBACK_MODELS`      | `openai/gpt-oss-20b:free,deepseek/deepseek-r1-distill:free,qwen/qwen3-32b:free` | Fallback model chain                          |
| `OPENROUTER_BASE_URL`             | `https://openrouter.ai/api/v1`                     | OpenRouter API base URL                              |
| `VECTOR_DB_TYPE`                  | `chroma`                                           | Vector database provider                             |
| `VECTOR_DB_PATH`                  | `data/vector_store`                                | Path to ChromaDB persistence directory               |
| `EMBEDDING_MODEL`                 | `sentence-transformers/all-MiniLM-L6-v2`           | Embedding model for RAG                              |
| `RAW_DATA_PATH`                   | `data/raw`                                         | Source raw data directory                            |
| `PROCESSED_DATA_PATH`             | `data/processed`                                   | Source processed data directory                      |
| `PROMOTIONS_CONTEXT_PATH`         | `data/promotions_context`                          | Copied RAG source documents directory                |
| `APP_NAME`                        | `GenAI Inventory Assistant`                        | Application display name                             |
| `APP_HOST`                        | `0.0.0.0`                                          | Backend bind host                                    |
| `APP_PORT`                        | `8000`                                             | Backend port                                         |
| `LOG_LEVEL`                       | `INFO`                                             | Backend logging level                                |
| `CORS_ORIGINS`                    | `http://localhost:5173,http://localhost:3000`      | Allowed frontend origins for CORS                    |
| `DEFAULT_FORECAST_HORIZON_DAYS`   | `30`                                               | Default forecast horizon in days                     |
| `DEFAULT_FORECASTER`              | `prophet`                                          | Default forecasting engine (`prophet` or `sarima`)   |
| `SAFETY_STOCK_MULTIPLIER`         | `1.5`                                              | Multiplier applied to calculated safety stock        |

---

## Re-running Data Ingestion

If you modify the source CSVs or want to rebuild the database from scratch:

```bash
# Recreate database tables and load all data
python -m src.ingestion.load

# Optionally load only a subset
python -m src.ingestion.load --only sales
python -m src.ingestion.load --only inventory
python -m src.ingestion.load --only sku
python -m src.ingestion.load --only supplier
python -m src.ingestion.load --only warehouse
python -m src.ingestion.load --only rag
```

If you update the knowledge documents used for RAG, rebuild the vector store:

```bash
python -m src.rag.ingest
```

Both commands are idempotent and use upserts for database records.

---

## Backend API Reference

All endpoints return JSON. The interactive API documentation is available at `http://localhost:8000/docs` and `http://localhost:8000/redoc`.

| Method | Path                                          | Tag          | Description                                                |
|--------|-----------------------------------------------|--------------|------------------------------------------------------------|
| GET    | `/`                                           | System       | API root and status page                                   |
| GET    | `/health`                                     | Health       | Backend health check                                       |
| GET    | `/api/skus`                                   | SKU          | List all SKUs, optionally filter by category               |
| GET    | `/api/skus/{sku_id}`                          | SKU          | Get a single SKU                                           |
| GET    | `/api/warehouses`                             | Warehouse    | List warehouse hubs                                        |
| GET    | `/api/inventory`                              | Inventory    | Latest inventory summary for each SKU-warehouse pair       |
| GET    | `/api/inventory/{sku_id}/{warehouse_id}/history` | Inventory | Inventory level history (default 90 days, max 365)       |
| GET    | `/api/sales/{sku_id}/{warehouse_id}`          | Sales        | Daily sales history (default 365 days, max 1000)           |
| GET    | `/api/dashboard`                              | Dashboard    | Aggregated dashboard summary                               |
| GET    | `/api/categories`                             | SKU          | Distinct SKU categories for filters                        |
| GET    | `/api/leadtimes/{sku_id}`                     | Supplier     | Supplier lead-time records for a SKU                       |
| POST   | `/api/forecast`                               | Forecasting | Generate Prophet or SARIMA forecast for a SKU/warehouse    |
| GET    | `/api/replenishment/alerts`                   | Replenishment | List low-stock and replenishment alerts                   |
| GET    | `/api/replenishment/{sku_id}/{warehouse_id}`  | Replenishment | Detailed ROP, safety stock, EOQ, and recommended order   |
| GET    | `/api/transfers/{sku_id}/{warehouse_id}`      | Transfers    | Evaluate inter-warehouse transfer opportunities            |
| POST   | `/api/whatif`                                 | What-If      | Run a stress-test scenario                                 |
| GET    | `/api/anomalies/{warehouse_id}`               | Anomalies    | Scan demand anomalies for a warehouse                      |
| GET    | `/api/rag/search`                             | RAG          | Search the ChromaDB knowledge base                         |
| POST   | `/api/chat`                                   | Chat         | Chat with the GenAI reasoning agent                        |
| GET    | `/api/approvals`                              | Approvals    | List human-in-the-loop approvals, optionally filtered      |
| POST   | `/api/approvals`                              | Approvals    | Create a new approval proposal                             |
| POST   | `/api/approvals/{approval_id}/review`         | Approvals    | Approve or reject an approval proposal                     |

### Request and response examples

**Forecast**

```json
POST /api/forecast
{
  "sku_id": "SKU_001",
  "warehouse_id": "WH_01",
  "horizon_days": 30,
  "model": "prophet"
}
```

**Chat**

```json
POST /api/chat
{
  "message": "Analyze SKU_001 stock status at WH_01",
  "conversation_id": "session-1"
}
```

**Approval review**

```json
POST /api/approvals/1/review
{
  "action": "approved",
  "reviewed_by": "manager",
  "edited_quantity": 200,
  "review_notes": "Approved after verifying seasonal demand."
}
```

---

## Frontend Views and Features

The React application is organized around six main views, all accessible through the sidebar.

### Dashboard

- KPI cards for critical deficit items, reorder warnings, active SKUs, and regional warehouses.
- Real-time replenishment and stockout alert table with filter by status and search by SKU or warehouse.
- Quick action buttons to open the AI reason, transfer evaluation, and forecast views for each alert.

### GenAI Demand and Inventory Copilot

- Natural-language chat interface powered by the `/api/chat` endpoint.
- Tool execution trace showing which inventory, forecast, transfer, and RAG tools were called.
- Action chips that jump to forecast, transfer, and what-if views when the message mentions a specific SKU or warehouse.

### Forecasting Engine

- Controls to choose SKU, warehouse, forecasting model (Prophet with festival regressors or SARIMA/exponential smoothing), and forecast horizon (14, 30, or 60 days).
- Metrics cards for projected horizon demand, average daily demand, backtest MAPE and RMSE, and active calendar regressors.
- Time-series chart with historical actuals, forecasted demand, and confidence bands.

### Inter-Warehouse Stock Rebalancing

- Evaluate transfer options for a given SKU and deficit warehouse.
- Compare transfer routes against external supplier purchase orders using distance, transit days, cost per unit, total cost, and time saved.
- Configure the requested quantity.

### What-If Scenario Stress Testing

- Simulate demand surges, supplier lead-time delays, and promotional lifts.
- View daily stock trajectory, projected vs. actual demand, unmet demand, stockout day, revenue at risk, and margin at risk.
- Receive a recommended safety stock adjustment.

### Human-in-the-Loop Approval Queue

- List pending, approved, and rejected approval proposals.
- Filter by status.
- Approve or reject proposals, optionally edit the proposed quantity, and add review notes.

---

## OpenRouter Configuration

The GenAI reasoning agent supports two operating modes.

### Live OpenRouter mode

1. Obtain an API key from OpenRouter.
2. Open `.env` in a text editor.
3. Set `OPENROUTER_API_KEY` to your key, for example:
   - `OPENROUTER_API_KEY=sk-or-v1-your-real-key-here`
4. Keep or change `OPENROUTER_MODEL` and `OPENROUTER_FALLBACK_MODELS` as desired.
5. Restart the backend server so the new settings are loaded.

When a valid key is present, the agent uses OpenRouter tool calling across the primary model and the fallback chain. If any model fails, it automatically tries the next model in the list.

### Simulation mode (default)

If `OPENROUTER_API_KEY` is empty or still set to the placeholder, the agent runs in smart heuristic simulation mode. It inspects the user message for SKU and warehouse identifiers and then calls the actual forecasting, replenishment, transfer, and RAG tools directly. This mode produces high-fidelity responses without requiring a network API key.

---

## Project Structure

```text
.
├── data/                          # SQLite database, raw/processed CSVs, vector store
│   ├── inventory.db               # SQLite database (created by ingestion)
│   ├── raw/                       # Raw source files
│   ├── processed/                 # Enriched source CSVs for ingestion
│   ├── metadata/                  # Warehouse metadata and distance/cost matrices
│   ├── rag_sources/               # Festival calendar and JSONL knowledge documents
│   ├── promotions_context/        # Copied RAG documents used at ingestion time
│   └── vector_store/              # ChromaDB persistence directory
├── frontend/                      # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── api.ts                 # Frontend API helpers
│   │   ├── App.tsx                # Main application shell and tab routing
│   │   ├── types.ts               # Shared TypeScript types
│   │   ├── components/            # Sidebar, Topbar, and shared components
│   │   └── views/                 # Dashboard, Chat, Forecast, Transfers, What-If, Approvals
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── src/                           # Python backend source
│   ├── api/                       # FastAPI routes, schemas
│   ├── config.py                  # Pydantic settings from .env
│   ├── database.py                # SQLite engine, session, init_db
│   ├── ingestion/                 # Data models and CSV loaders
│   ├── forecasting/               # Prophet and SARIMA engines
│   ├── replenishment/             # ROP, safety stock, EOQ calculator
│   ├── warehouse/                 # Inter-warehouse transfer engine
│   ├── whatif/                    # Scenario simulation engine
│   ├── anomaly/                   # Anomaly detection engine
│   ├── rag/                       # ChromaDB store, retriever, ingestion
│   ├── reasoning/                 # GenAI reasoning agent and tool integration
│   └── tools/                     # Inventory tools used by the reasoning agent
├── .env.example                   # Template for environment variables
├── .gitignore                     # Ignored files and directories
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── RUNBOOK.md                     # Runbook and documentation
├── start_dev.ps1                  # Windows one-click startup script
└── pyproject.toml                 # Project metadata and dependencies
```

---

## Development Commands

### Backend

- Start the backend with hot reload:
  - `uvicorn src.api.main:app --reload --port 8000`
- Load data into SQLite:
  - `python -m src.ingestion.load`
- Rebuild the vector store:
  - `python -m src.rag.ingest`
- Run the application from the project root without installing a virtual environment (not recommended):
  - `pip install -r requirements.txt && uvicorn src.api.main:app --reload --port 8000`

### Frontend

- Start the dev server:
  - `cd frontend && npm run dev`
- Lint the TypeScript code:
  - `cd frontend && npm run lint`
- Build for production:
  - `cd frontend && npm run build`
- Preview the production build:
  - `cd frontend && npm run preview`

### Git workflow

The repository uses a single main branch for the full system. Commit changes with clear messages. The project stores its SQLite database, virtual environment, and `node_modules` inside `.gitignore`, so these do not need to be committed.

---

## Troubleshooting

- **Port 8000 already in use**: Change the backend port with `--port 8001` or set `APP_PORT=8001` in `.env`.
- **Port 5173 already in use**: Change the Vite port in `frontend/vite.config.ts` or pass `--port 5174`.
- **Python native package installation fails on Windows**: Install Visual Studio Build Tools with the "Desktop development with C++" workload, then run `pip install --force-reinstall <package>` for the failing package.
- **SQLite database not found after cloning**: The database is in `.gitignore`. Run `python -m src.ingestion.load` to rebuild it.
- **ChromaDB documents not found during chat**: Run `python -m src.rag.ingest` to rebuild the vector store, then restart the backend.
- **".env" not loading settings**: Verify that `.env` is at the project root (not inside `frontend`) and that variables match the names listed in the Environment Variables table.
- **Frontend cannot reach the backend**: Ensure the backend is running on `localhost:8000` and that the Vite proxy is configured for `/api` and `/health` in `frontend/vite.config.ts`.
- **CORS errors**: The backend CORS origins are controlled by `CORS_ORIGINS` in `.env`. The default allows `http://localhost:5173` and `http://localhost:3000`.
- **OpenRouter returns empty responses**: Verify that the API key has sufficient balance, that the model IDs are correct, and that the backend was restarted after editing `.env`.

---

## License

MIT
