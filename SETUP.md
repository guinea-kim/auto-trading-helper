# Project Setup Guide

This document guides you through setting up the development environment for `auto-trading-helper`.

## Python Environment Setup

### 1. Prerequisites
- **Python 3.10+**: Ensure Python 3.10 or higher is installed. The project is currently running on Python 3.10.16.

### 2. Virtual Environment
It is recommended to use a virtual environment to manage dependencies.

**Create a virtual environment:**
```bash
python3 -m venv venv
```

**Activate the virtual environment:**
- MacOS/Linux:
  ```bash
  source venv/bin/activate
  ```
- Windows:
  ```bash
  .\venv\Scripts\activate
  ```

### 3. Install Dependencies
Install the required packages using `pip` and the provided `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 4. Environment Variables
This project uses a `.env` file for configuration and secrets.
Create a `.env` file in the project root. Please refer to `.gemini/GEMINI.md` for the list of required variables and their descriptions.

---
*Additional environment setup instructions will be added after server environment review.*
