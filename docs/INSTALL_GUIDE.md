# 🛠️ RAG-Destroyer: Installation & Setup Guide

*This guide is written in English.*

Welcome to the **Industrial RAG-Destroyer (Zero-Vector-DB)**. This guide will help you set up the system from scratch in less than 5 minutes.

---

## 📋 Prerequisites
- **Python 3.9+**
- **Obsidian** (Optional, for managing your Markdown knowledge silos)
- **API Key** (Gemini, OpenAI, or Anthropic)

---

## 🚀 Step 1: Clone & Install
```bash
git clone https://github.com/vittaya1973/RAG-Destroyer.git
cd RAG-Destroyer
pip install -r requirements.txt
```

---

## 🔌 Step 2: The "Plug & Play" Valve Setup

When you start the app, go to the **🛠️ System Config** page.

### 1. Link your AI Provider
RAG-Destroyer supports multiple providers. Select your favorite and paste your key:
- **Google Gemini** (Recommended for speed/cost)
- **OpenAI GPT-4o**
- **Anthropic Claude 3.5**

### 2. Connect your Knowledge Vault
Set the paths to your local folders:
- **Raw Data Ingestion**: Where you drop your raw PDFs or Text files.
- **Knowledge Vault**: Where the AI stores the "Cleaned" and "Tagged" research documents.

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
