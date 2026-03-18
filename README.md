# 🤖 AI Trading Signal Engine

> An end-to-end pipeline that fetches financial news, classifies it with a Google Gemini LLM, generates actionable trading signals, and evaluates them against a live simulated portfolio — all visualised in a Streamlit dashboard.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-orange?logo=google)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red?logo=streamlit)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Pipeline Architecture](#pipeline-architecture)
3. [Features](#features)
4. [Project Structure](#project-structure)
5. [Installation](#installation)
6. [Google Gemini API Setup](#google-gemini-api-setup)
7. [Running the Project](#running-the-project)
8. [Key Concepts](#key-concepts)
9. [Performance Tracking & Backtesting](#performance-tracking--backtesting)
10. [Known Limitations](#known-limitations)
11. [Future Improvements](#future-improvements)

---

## Overview

**AI Trading Signal Engine** is a fully automated, research-grade trading signal system built in Python. It ingests raw financial news from public sources, filters for market-relevant content, and feeds it to a **Google Gemini** large language model that classifies sentiment and generates structured trading signals.

Each signal is then compared against the current simulated portfolio (stored in `portfolio.json`) to decide the optimal action: open a new position, add to an existing one, reduce exposure, or hold. Historical signal performance is persisted in a **SQLite** database and exposed through an interactive **Streamlit** dashboard.

---

## Pipeline Architecture

```
┌─────────────────────┐
│   News Fetcher      │  ← Pulls articles from financial news sources
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   News Filter       │  ← Removes irrelevant / non-tradable articles
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Gemini LLM Engine  │  ← Classifies sentiment, extracts asset & signal
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Signal Generator   │  ← Produces BUY/SELL signals with confidence
│                     │    and recommended position size
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Portfolio Evaluator │  ← Reads portfolio.json, prevents duplicate
│                     │    trades, emits HOLD/ADD/REDUCE/OPEN decisions
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Backtest & DB      │  ← Stores signals, evaluates P&L, tracks metrics
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Streamlit Dashboard │  ← Real-time visualisation of signals & performance
└─────────────────────┘
```

---

## Features

- 📰 **Automated news ingestion** — periodically fetches financial news from configured sources
- 🔍 **Intelligent filtering** — discards noise and keeps only market-moving, actionable articles
- 🧠 **LLM-powered classification** — leverages Google Gemini to understand article context and extract structured signals
- 📈 **Structured trading signals** — each signal includes asset ticker, direction (BUY/SELL), confidence score (0–100 %), and recommended position size
- 💼 **Portfolio-aware decisions** — cross-references active positions to avoid redundant trades and suggest the most appropriate action
- 🔄 **Duplicate trade prevention** — detects open positions and routes to HOLD, ADD, or REDUCE instead of blindly opening new ones
- 🧪 **Backtesting engine** — simulates signal performance against historical price data
- 🗄️ **SQLite persistence** — all signals and outcomes are stored for audit and analysis
- 📊 **Streamlit dashboard** — interactive UI displaying live signals, portfolio state, and performance metrics

---

## Project Structure

```
IA-Invest/
├── dashboard/
│   └── dashboard.py          # Streamlit dashboard entry point
├── engine/
│   ├── fetcher.py            # News article fetcher
│   ├── filter.py             # Relevance filter for articles
│   ├── classifier.py         # Gemini LLM classifier & signal extractor
│   ├── signal_generator.py   # Builds structured signal objects
│   ├── portfolio_evaluator.py# Compares signals against portfolio.json
│   └── backtester.py         # Backtesting & P&L simulation
├── db/
│   └── database.py           # SQLite schema & query helpers
├── portfolio.json            # Simulated portfolio (current positions)
├── run.py                    # Main entry point
├── requirements.txt          # Python dependencies
└── README.md
```

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/14miguels/IA-Invest.git
cd IA-Invest
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# or
.venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Google Gemini API Setup

The signal classification engine is powered by **Google Gemini**. Follow these steps to obtain and configure your API key.

### Get Your API Key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **"Create API Key"** and copy the generated key

### Configure the Environment Variable

Create a `.env` file in the project root (or export it in your shell):

```bash
# .env
GEMINI_API_KEY=your_api_key_here
```

Or export it directly:

```bash
export GEMINI_API_KEY="your_api_key_here"   # Linux / macOS
# or
set GEMINI_API_KEY=your_api_key_here         # Windows CMD
```

> ⚠️ **Never commit your API key to version control.** The `.env` file is listed in `.gitignore`.

---

## Running the Project

### Debug Mode

Runs the pipeline on a small sample of articles and prints verbose output — ideal for development and troubleshooting.

```bash
python run.py --mode debug
```

### Full Pipeline

Executes the complete end-to-end flow: fetch → filter → classify → evaluate → store.

```bash
python run.py
```

### Streamlit Dashboard

Launches the interactive dashboard to visualise signals, portfolio state, and performance metrics.

```bash
streamlit run dashboard/dashboard.py
```

Open your browser at [http://localhost:8501](http://localhost:8501).

---

## Key Concepts

### Signals

A **signal** is a structured recommendation produced by the LLM engine after analysing a financial news article. Each signal contains:

| Field           | Description                                           |
|-----------------|-------------------------------------------------------|
| `asset`         | Ticker or commodity name (e.g., `AAPL`, `GOLD`)       |
| `action`        | Direction of the trade — `BUY` or `SELL`              |
| `confidence`    | Model's certainty from `0` (low) to `100` (high)      |
| `position_size` | Suggested allocation as a percentage of capital       |
| `rationale`     | Short explanation derived from the article            |

### Position Size

Position size is calculated by the signal generator based on the confidence score and a configurable maximum allocation per asset. Higher-confidence signals produce proportionally larger recommended sizes, with a hard cap to enforce risk limits.

### Portfolio Decisions

When the portfolio evaluator compares a new signal against `portfolio.json`, it can emit one of the following decisions:

| Decision                  | Meaning                                                          |
|---------------------------|------------------------------------------------------------------|
| `OPEN_POSITION`           | No existing position — safe to enter a new trade                 |
| `ADD_TO_POSITION`         | Existing position in the same direction — increase exposure      |
| `REDUCE_POSITION`         | Signal conflicts with current position — reduce or hedge         |
| `HOLD_EXISTING_ORDER`     | Signal duplicates an already-active trade — no action needed     |
| `INSUFFICIENT_CONFIDENCE` | Confidence below threshold — skip to avoid low-quality trades    |

---

## Performance Tracking & Backtesting

All generated signals are persisted in a local **SQLite** database (`signals.db`) with their full metadata and timestamps. The backtesting engine:

1. **Replays** historical signals against closing price data
2. **Calculates P&L** for each signal based on entry and exit prices
3. **Tracks metrics** such as win rate, average return, and maximum drawdown
4. **Exposes results** through the Streamlit dashboard for easy analysis

The database schema stores enough context to reconstruct and re-evaluate any past signal, supporting continuous improvement of the classification model.

---

## Known Limitations

- 🚫 **No real broker execution** — the engine generates signals only; no orders are sent to any brokerage or exchange
- 🗺️ **Asset mapping gaps** — some commodity names (e.g., `ALUMINUM`) may not map cleanly to tradable tickers and are skipped or flagged
- 📡 **News source dependency** — signal quality is tied to the availability and freshness of configured news feeds
- 🕐 **No intraday data** — the backtester currently operates on daily closing prices, which may not reflect realistic entry/exit slippage
- 🌐 **API rate limits** — high-frequency runs may hit Google Gemini API quota limits; implement exponential backoff if needed

---

## Future Improvements

- 🔌 **Broker integration** — connect to brokers via APIs (e.g., Alpaca, Interactive Brokers) for automated order execution
- ⚡ **Real-time execution engine** — process news streams in near real-time using WebSocket feeds
- 🛡️ **Advanced risk management** — implement stop-loss, take-profit, and portfolio-level drawdown controls
- 🤖 **Model fine-tuning** — fine-tune the LLM on domain-specific financial datasets to improve classification accuracy
- 📦 **Docker deployment** — containerise the full stack for reproducible, one-command deployment
- 🔔 **Alerting system** — send signal notifications via Slack, Telegram, or email
- 📐 **Multi-asset correlation** — detect correlated signals to avoid over-concentration in related assets

---

## License

This project is licensed under the [MIT License](LICENSE).

