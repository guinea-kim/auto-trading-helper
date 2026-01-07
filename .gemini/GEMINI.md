# Gemini Configuration and Setup Guide

This document outlines the environment setup and configuration standards for the `auto-trading-helper` project, specifically for Gemini agents.

## Environment Setup

### 1. Python Virtual Environment
We use a local virtual environment named `venv` to manage dependencies. This ensures consistency with the server environment.

**To activate the environment:**
```bash
source venv/bin/activate
```

**To install/update dependencies:**
```bash
pip install -r requirements.txt
```
*Note: `requirements.txt` is pinned to specific versions to match the production server.*

### 2. Environment Variables (.env)
We use a `.env` file to manage secrets and configuration. This replaces the hardcoded values in `library/secret.py` for local development.

**File Path:** `.env` (in project root)

**Required Variables:**
- **General:** `APP_SECRET`
- **Database:** `DB_NAME`, `DB_NAME_KR`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`
- **Alerts:** `ALERT_EMAIL`, `ALERT_PASSWORD`, `ALERTED_EMAIL`
- **Schwab API:**
  - `SCHWAB_TUCAN_APP_KEY`, `SCHWAB_TUCAN_SECRET`
  - `SCHWAB_GUINEA_APP_KEY`, `SCHWAB_GUINEA_SECRET`
- **Korea Investment API:**
  - `KR_TUCAN_APP_KEY`, `KR_TUCAN_SECRET`

**Usage Pattern:**
Gemini should check `.env` for credentials before modifying `secret.py` or running scripts that require authentication.
