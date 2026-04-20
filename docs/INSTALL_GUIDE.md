# 🛠️ RAG-Destroyer: Installation & Setup Guide

*This guide is written in English.*

Welcome to the **Industrial RAG-Destroyer (Zero-Vector-DB)**. This guide will help you set up the system from scratch in less than 5 minutes.

---

## 📋 Prerequisites
- **Python 3.9+**
- **Obsidian** (Optional, for managing your Markdown knowledge silos)
- **API Key** (Gemini, OpenAI, or Anthropic)
- **Pandoc** (Optional — only if you use export paths that call `pypandoc`; see [pandoc.org](https://pandoc.org/installing.html))

---

## 🚀 Step 1: Clone & Install
```bash
git clone https://github.com/tong-mini-mac/RAG-Destroyer.git
cd RAG-Destroyer
pip install -r requirements.txt
```

---

## 🔌 Step 2: The "Plug & Play" Valve Setup

Start the app first — **no `config/.env` is required** for a quick trial.

When the UI is open, go to **🛠️ System Config**.

### 1. Link your AI provider (BYOK)
RAG-Destroyer supports multiple providers. Select one and paste **your own** API key (keys stay in this browser session unless you choose **Save keys to config/.env**):

- **Google Gemini** (recommended for speed/cost)
- **OpenAI GPT-4o**
- **Anthropic Claude 3.5**

See `config/.env.example` if you prefer file-based configuration.

### 2. Connect your knowledge vault (optional)
Set the paths to your local folders:

- **Raw Data Ingestion**: Where you drop your raw PDFs or Text files.
- **Knowledge Vault**: Where the AI stores the "Cleaned" and "Tagged" research documents.

Click **Apply storage paths** if you change defaults; restart Streamlit if the background file watcher should use a new raw folder.

### CLI scripts (`run_qc_field_trial.py`, etc.)

Outside Streamlit there is no session state. Set **`RAGD_PRIMARY_PROVIDER`** to `google`, `openai`, or `anthropic` in `config/.env` (or export it), and provide the matching API key. Saving keys from the app’s **System Config** also writes `RAGD_PRIMARY_PROVIDER` for you.

---

## 🤖 Step 3: Running the Librarian

### Start the UI
```bash
streamlit run app.py
```

### Automatic Monitoring
The system includes a **Background Watchdog**. Once running:
1. Drop a file into your `raw_data` folder.
2. The Librarian will automatically pick it up, refine it, and move it to the correct department in the `knowledge` vault.
3. You can immediately start asking questions about that document in the **🧠 GURU Assistant**.

---

## 🛡️ Privacy & Security
- **Local-First**: Your documents never leave your machine except during AI synthesis.
- **Zero-Vector-DB**: No third-party vector databases are used.
- **Silo Isolation**: RBAC is enforced at the file-system level.

---
**Enjoy the Industrial Power of Deterministic RAG!** 🚀🏛️
