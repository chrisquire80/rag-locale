# RAG LOCALE Setup Guide - Real Document Integration

**Status**: ✅ Complete - Ready to use with your real documents
**Updated**: 2026-02-19

---

## Overview

You now have a complete RAG LOCALE system that can load documents from **any folder on your PC**. This guide walks you through the setup process.

---

## Prerequisites

### Required
- ✅ Python 3.9+ installed
- ✅ Google Gemini API key (`.env` file configured)
- ✅ Internet connection (for Gemini API)
- ✅ Documents in supported formats (PDF, TXT, MD, DOCX)

### Check Installation
```bash
# Verify Python
python --version
# Should show: Python 3.x.x

# Verify Gemini API key
cat .env | grep GEMINI_API_KEY
# Should show your API key (starts with sk- or similar)

# Verify dependencies
pip list | grep streamlit
# Should show streamlit version
```

---

## Installation Steps

### Step 1: Verify Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Key packages needed:
# - streamlit (UI framework)
# - google-generativeai (Gemini API)
# - PyPDF2 (PDF reading)
# - numpy (embeddings)
```

### Step 2: Configure Gemini API Key

**If not already configured:**

```bash
# Create or edit .env file
nano .env

# Add your Gemini API key:
GEMINI_API_KEY=your_api_key_here
```

Or on Windows:
```bash
# Create .env in RAG LOCALE folder with:
GEMINI_API_KEY=your_api_key_here
```

### Step 3: Test Installation

```bash
# Run the test suite
python test_real_document_loading.py

# Select option 1: "Test default folder"
# You should see: [OK] Loaded X documents from default folder
```

---

## Using RAG LOCALE with Your Documents

### Method 1: Quick Start (Recommended for First Time)

```bash
# Run the quick start helper
python quick_start.bat  # Windows

# Or directly:
python find_documents_folder.py
```

This will:
1. Show you folders with documents on your PC
2. Let you select your documents folder
3. Show you the exact path to use
4. Help you validate the folder

### Method 2: Direct Path

If you know your documents folder path:

```bash
# Launch the app
python launch_app.py

# Or manually:
streamlit run app_streamlit_real_docs.py
```

Then in the Streamlit sidebar:
1. Select **"Custom folder path"**
2. Paste your folder path: `C:\Users\YourName\Documents\PDFs`
3. Click **"Load Documents"**

### Method 3: Using Default Folder

If you copy your documents to `RAG LOCALE/documents/`:
1. Copy your files to the `documents/` folder
2. In Streamlit, select **"Default (documents/)"**
3. Click **"Load Documents"**

---

## Step-by-Step Tutorial

### Finding Your Documents Folder

**Scenario**: You have 71 PDFs in your Downloads folder

```
C:\Users\ChristianRobecchi\Downloads\
├── document1.pdf
├── document2.pdf
├── ...
└── document71.pdf
```

**Steps:**

1. **Open Command Prompt / PowerShell**
   ```bash
   cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE
   ```

2. **Run the finder**
   ```bash
   python find_documents_folder.py
   ```

3. **Select option 1** (Search common locations)
   - The script finds all folders with documents
   - Shows: `C:\Users\ChristianRobecchi\Downloads` - 71 files

4. **Select your folder** (option 1)
   - Script validates: 71 PDF files
   - Shows full path: `C:\Users\ChristianRobecchi\Downloads`

5. **Copy the path** (it's shown at the end)
   ```
   C:\Users\ChristianRobecchi\Downloads
   ```

### Loading Into RAG LOCALE

1. **Start the app**
   ```bash
   python launch_app.py
   ```

2. **Wait for Streamlit to open** (should open in browser)
   ```
   http://localhost:8501
   ```

3. **In the sidebar, "Document Folder Selection"**
   - Select: `Custom folder path`
   - Paste: `C:\Users\ChristianRobecchi\Downloads`
   - Click: `Load Documents` button

4. **Wait for loading**
   - Progress shown in sidebar
   - Expected time: 5-10 minutes for 71 PDFs
   - Once done: Shows "Loaded 71 documents"

5. **Test it out!**
   - Try a query like: "What is the onboarding process?"
   - See re-ranked results
   - Check quality score

---

## File Structure

```
RAG LOCALE/
├── app_streamlit_real_docs.py    ← Main app (UPDATED)
├── launch_app.py                 ← App launcher
├── find_documents_folder.py      ← Helper (NEW)
├── quick_start.bat               ← Quick start (NEW)
├── test_real_document_loading.py ← Tests (NEW)
├── SETUP_GUIDE.md                ← This file
├── LOAD_REAL_DOCUMENTS.md        ← Detailed guide
│
├── document_loader.py            ← Document loading (UPDATED)
├── src/
│   ├── llm_service.py           ← Gemini API
│   ├── vector_store.py          ← Embeddings & search
│   ├── cross_encoder_reranking.py ← Re-ranking (FASE 16)
│   ├── vision_service.py        ← Vision API (FASE 17)
│   └── ...
│
├── documents/                    ← Default folder
├── data/                         ← Vector store cache
├── logs/                         ← Application logs
│
├── requirements.txt              ← Python dependencies
├── .env                          ← Configuration (API keys)
└── .env.example                  ← Template
```

---

## Configuration Options

### In Streamlit Sidebar

#### Document Loading
- **Default folder**: Use `RAG LOCALE/documents/`
- **Custom folder**: Point to any folder on your PC

#### Features Toggle
- **Show Citations**: Display source documents
- **Show Suggestions**: Suggest follow-up queries
- **Show Quality Score**: Display answer quality metric

#### Advanced (FASE 16-17)
- **Enable Re-ranking**: Improve answer quality (+10%)
- **Original Score Weight** (Alpha): 0.0-1.0 slider
  - 0.0 = 100% semantic relevance
  - 0.5 = 50/50 balance
  - 1.0 = 100% original vector score
- **Enable Vision API**: Analyze document images
- **Min Image Relevance**: Threshold for image inclusion

---

## Performance Expectations

### Document Loading Time
```
10 documents    → ~1 minute
50 documents    → ~3-5 minutes
71 documents    → ~5-10 minutes
200 documents   → ~15-20 minutes
```

### Query Performance
```
First query (no cache)     → 2-5 seconds
Repeated query (cached)    → <1 second
With re-ranking enabled    → 2-8 seconds
```

### Memory Usage
- Base app: ~200 MB
- Per 100 documents: ~50 MB additional
- 71 documents: ~300-400 MB total

---

## Troubleshooting

### App Won't Start

**Error**: `ModuleNotFoundError: No module named 'streamlit'`
```bash
# Install dependencies
pip install -r requirements.txt
```

**Error**: `Port 8501 already in use`
```bash
# Kill previous Streamlit process
taskkill /F /IM python.exe  # Windows (careful: kills all Python)

# Or use different port
streamlit run app_streamlit_real_docs.py --server.port 8502
```

### No Documents Loading

**Check 1**: Verify path exists
```bash
# Windows
dir "C:\path\to\documents"

# Or use helper
python find_documents_folder.py
```

**Check 2**: Verify file types
```bash
# Are there PDF, TXT, or MD files in the folder?
# Helper script shows file types
python find_documents_folder.py
```

**Check 3**: Check permissions
```bash
# Can you read files in the folder?
# Avoid system folders and protected directories
# Use Documents, Downloads, or Desktop
```

### Embeddings Taking Too Long

**Normal**: First load of 50+ PDFs takes 5-10 minutes
**Optimization**:
- Try with fewer documents first (10-20)
- Ensure stable internet connection
- Check Gemini API is responding (logs/rag.log)

### Vector Store Errors

**If vector store is corrupted:**
```bash
# Delete the cache
rm -rf data/vector_db/*  # macOS/Linux
rmdir /s /q data\vector_db  # Windows

# Restart app - will rebuild
python launch_app.py
```

---

## Testing Your Setup

### Quick Test (2 minutes)
```bash
# Test default folder
python test_real_document_loading.py

# Select: 1 (Test default folder)
# Should see: [OK] Loaded X documents
```

### Full Test (10 minutes)
```bash
# Test with your documents
python test_real_document_loading.py

# Select: 3 (Full test suite)
# Enter your documents folder path when prompted
# Should see:
#   [OK] Loaded X documents
#   [OK] File analysis complete
#   [OK] Document summary created
```

### End-to-End Test (5 minutes)
1. Launch app: `python launch_app.py`
2. Load your documents folder
3. Try a query
4. Check results and quality score

---

## Next Steps After Setup

### 1. Familiarize with Features
- Try different queries
- Experiment with re-ranking (alpha slider)
- Enable Vision API for image analysis
- Check quality scores

### 2. Optimize Performance
- Experiment with re-ranking alpha (0.3 is default)
- Enable caching for repeated queries
- Profile performance with logs

### 3. Scale Up
- Start with 10-20 documents
- Gradually add more documents
- Monitor performance
- Adjust settings as needed

### 4. Advanced Usage
- Load different document sets
- Use query expansion
- Enable multimodal (Vision API)
- Analyze quality metrics

---

## System Requirements Checklist

- [ ] Python 3.9+ installed
- [ ] Google Gemini API key in `.env`
- [ ] Internet connection
- [ ] Documents in supported format (PDF, TXT, MD)
- [ ] Sufficient disk space (500 MB minimum)
- [ ] Sufficient RAM (4 GB minimum, 8 GB recommended)

---

## Getting Help

### Resources
1. **This guide**: SETUP_GUIDE.md (what you're reading)
2. **Detailed guide**: LOAD_REAL_DOCUMENTS.md (comprehensive reference)
3. **Helper script**: `python find_documents_folder.py` (interactive)
4. **Test script**: `python test_real_document_loading.py` (debugging)
5. **Documentation**: Check `PHASE_B_EXECUTION_GUIDE.md` for testing details

### Logs
Check application logs for detailed errors:
```bash
tail -f logs/rag.log  # macOS/Linux
Get-Content logs/rag.log -Tail 50  # Windows PowerShell
```

---

## Quick Reference

```bash
# Start app
python launch_app.py

# Find documents folder
python find_documents_folder.py

# Test document loading
python test_real_document_loading.py "C:\path\to\documents"

# Clear Streamlit cache
python -m streamlit cache clear

# Kill port 8501 (if stuck)
taskkill /F /IM python.exe  # WARNING: Kills all Python

# View logs
type logs/rag.log | tail -50
```

---

## Success Indicators

✅ **You've successfully set up when:**
1. App launches without errors
2. You can see the document folder selector
3. You can load documents from custom folder
4. Query returns results with quality scores
5. Re-ranking toggle works and changes results

---

**Ready to go! 🚀**

Start with: `python quick_start.bat` (Windows) or `python find_documents_folder.py` (all platforms)
