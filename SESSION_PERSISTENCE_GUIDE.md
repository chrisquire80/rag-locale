# Session Persistence System - RAG LOCALE

## Overview

The Session Persistence System automatically saves and restores the complete state of your RAG LOCALE application between restarts. This eliminates the need to reconfigure folders and reload documents every time you restart the app.

## What Gets Persisted

### 1. **Document Folder Selection** 📁
- **What**: The folder path you select containing your documents
- **Storage**: `data/session_persistence/user_settings.json`
- **Behavior**: Automatically remembered and pre-selected on next startup
- **Validation**: Checks if path still exists before restoring

### 2. **Loaded Documents** 📄
- **What**: All documents loaded from your folder (metadata, content, embeddings)
- **Storage**: `data/session_persistence/documents_cache.json`
- **Behavior**: Instantly available on restart without re-scanning folder
- **Cache Keys**: Hash-based content matching for efficient updates

### 3. **Conversation History** 💬
- **What**: All past queries, responses, and interactions
- **Storage**: `data/session_persistence/current_session.json`
- **Behavior**: Full conversation context preserved
- **Size**: Grows with usage, but manageable for most workflows

### 4. **Topic Analysis** 🏷️
- **What**: Document topics, groupings, and statistical analysis
- **Storage**: `data/session_persistence/` + `data/topics_cache/`
- **Behavior**: Topic categories and document groupings instantly available
- **Methods**: Supports LLM-based, keyword, and clustering approaches

### 5. **Application Settings** ⚙️
- **What**: User preferences and application state
- **Storage**: `data/session_persistence/user_settings.json`
- **Behavior**: Maintains UI state across sessions
- **Includes**: Sidebar state, tab selections, filter preferences

### 6. **Simulation Variables** 📊
- **What**: Any custom variables used in forecasting/simulation
- **Storage**: `data/session_persistence/current_session.json`
- **Behavior**: Preserved for consistent analysis workflows

## Directory Structure

```
RAG LOCALE/
├── data/
│   ├── session_persistence/          ← Main persistence directory
│   │   ├── current_session.json       ← Conversation & state (updated continuously)
│   │   ├── documents_cache.json       ← Loaded documents (updated on folder change)
│   │   └── user_settings.json         ← Folder selection & preferences (updated on change)
│   │
│   └── topics_cache/                 ← Topic analysis cache
│       └── topics_cache.json          ← Extracted topics (updated on analysis)
│
├── session_persistence.py             ← Core persistence module
├── document_topic_analyzer.py          ← Topic extraction & analysis
├── topic_ui_renderer.py                ← UI components for topics
└── app_streamlit_real_docs.py         ← Main app (uses persistence)
```

## How It Works

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│          Application Startup (app_streamlit_real_docs.py)  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  initialize_session()          │
        │  (Restores previous state)     │
        └────────────┬───────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  SessionPersistence.load_session_ │
        │  _state()                         │
        └────────────┬──────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  SessionPersistence.get_cached_  │
        │  _documents()                    │
        └────────────┬──────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  SessionPersistence.get_last_    │
        │  _documents_dir()                │
        └────────────┬──────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  App Ready with:                 │
        │  - Previous folder selected      │
        │  - Documents cached & loaded     │
        │  - Conversation history restored │
        │  - Settings intact               │
        └────────────────────────────────────┘
```

### File Operations

#### Saving (Happens Continuously)

1. **On Folder Selection** (`load_documents_real()`)
   ```python
   persistence.save_documents_dir(documents_dir)
   persistence.save_documents(documents_list, documents_dir)
   ```
   - Saves folder path to `user_settings.json`
   - Caches all documents to `documents_cache.json`

2. **During Interaction** (`main()` function)
   ```python
   persistence.save_session_state(st.session_state)
   ```
   - Saves conversation history
   - Saves current application state
   - Updates at end of each render

3. **On Topic Analysis**
   ```python
   analyzer.extract_topics_hybrid(documents)
   # Topics automatically saved via DocumentTopicAnalyzer
   ```
   - Caches extracted topics
   - Saves groupings and statistics

#### Loading (Happens at Startup)

1. **Initialize Session**
   ```python
   persistence = SessionPersistence()
   saved_state = persistence.load_session_state()
   cached_docs = persistence.get_cached_documents()
   last_dir = persistence.get_last_documents_dir()
   ```

2. **Restore State**
   - Set session state variables from saved data
   - Load documents from cache if available
   - Pre-select previously used folder

## Core Components

### 1. SessionPersistence Class

**Location**: `session_persistence.py`

#### Key Methods

| Method | Purpose | Input | Output |
|--------|---------|-------|--------|
| `save_documents_dir()` | Save selected folder path | folder_path: str | None |
| `get_last_documents_dir()` | Retrieve saved folder | None | folder_path: str or None |
| `save_documents()` | Cache loaded documents | documents: List, folder: str | None |
| `get_cached_documents()` | Retrieve cached documents | None | dict with documents |
| `save_session_state()` | Save conversation & settings | session_state: Dict | None |
| `load_session_state()` | Restore previous session | None | session_state: Dict or None |
| `get_cache_info()` | Get cache statistics | None | info: Dict |
| `clear_session_cache()` | Delete all cached data | None | None |

#### Usage Example

```python
from session_persistence import SessionPersistence

# Initialize
persistence = SessionPersistence()

# Save folder selection
persistence.save_documents_dir("/path/to/documents")

# Save documents
persistence.save_documents(documents_list, "/path/to/documents")

# Retrieve on startup
cached_docs = persistence.get_cached_documents()
last_folder = persistence.get_last_documents_dir()

# Check cache status
info = persistence.get_cache_info()
print(f"Documents cached: {info['docs_count']}")
print(f"Saved at: {info['docs_saved_at']}")

# Clear if needed
persistence.clear_session_cache()
```

### 2. DocumentTopicAnalyzer Integration

**Location**: `document_topic_analyzer.py`

The topic analyzer automatically caches extracted topics:

```python
analyzer = DocumentTopicAnalyzer(llm_service=None, cache_enabled=True)

# Extract topics (cached automatically)
topics, grouped_docs, stats = analyzer.analyze_documents(
    documents,
    method="hybrid"
)

# Topics are saved to data/topics_cache/topics_cache.json
# On next run, topics for same documents are loaded from cache
```

### 3. TopicUIRenderer Integration

**Location**: `topic_ui_renderer.py`

Renders persisted topic data in 7 different views:

```python
from topic_ui_renderer import TopicUIRenderer

# Filter sidebar (uses persisted topics)
selected_topic = TopicUIRenderer.render_topic_filter_sidebar(
    grouped_docs,
    stats
)

# Topics tab views
TopicUIRenderer.render_topics_tab(grouped_docs, stats)
TopicUIRenderer.render_topics_tree(grouped_docs, stats)
TopicUIRenderer.render_topics_cards(grouped_docs, stats)
TopicUIRenderer.render_topic_distribution_chart(stats)
TopicUIRenderer.render_topic_search(grouped_docs)
```

### 4. Main App Integration

**Location**: `app_streamlit_real_docs.py`

Three integration points:

#### Point 1: initialize_session()
```python
def initialize_session() -> None:
    persistence = SessionPersistence()

    # Load previous session
    saved_state = persistence.load_session_state()
    if saved_state:
        # Restore conversation, settings, etc.
        for key, value in saved_state.items():
            st.session_state[key] = value

    # Load cached documents
    cached_docs = persistence.get_cached_documents()
    if cached_docs:
        st.session_state.documents = cached_docs['documents']
        st.session_state.documents_loaded = True

    # Pre-select folder
    last_folder = persistence.get_last_documents_dir()
    if last_folder:
        st.session_state.last_docs_dir = last_folder
```

#### Point 2: load_documents_real()
```python
def load_documents_real(documents_dir: str):
    # ... load documents ...

    # Save to cache
    persistence = SessionPersistence()
    persistence.save_documents_dir(documents_dir)
    persistence.save_documents(st.session_state.documents, documents_dir)
```

#### Point 3: main()
```python
def main():
    # ... app logic ...

    # Save state after each render
    persistence = SessionPersistence()
    persistence.save_session_state(st.session_state)
```

## File Formats

### user_settings.json
```json
{
  "last_documents_dir": "./documents/my_files",
  "last_updated": "2026-02-20T17:40:09.735000",
  "last_updated_timestamp": 1708437609.735
}
```

### documents_cache.json
```json
{
  "documents": [
    {
      "id": "doc_001",
      "text": "Document content...",
      "metadata": {
        "filename": "document.txt",
        "size": 2048
      }
    }
  ],
  "docs_dir": "./documents/my_files",
  "count": 1,
  "saved_at": "2026-02-20T17:40:09.735000",
  "timestamp": 1708437609.735
}
```

### current_session.json
```json
{
  "conversation_history": [
    {
      "role": "user",
      "content": "What is in these documents?"
    },
    {
      "role": "assistant",
      "content": "Based on the documents..."
    }
  ],
  "quality_scores": [0.85, 0.92],
  "conversation_id": "conv_123456",
  "last_docs_dir": "./documents/my_files",
  "custom_docs_path": "",
  "simulation_vars": {
    "cost_variation": 0,
    "revenue_variation": 0
  },
  "topic_grouped": {...},
  "topic_stats": {...},
  "saved_at": "2026-02-20T17:40:09.735000"
}
```

## Common Operations

### 1. Clear Cache Completely

If you want to start fresh without cached data:

```python
from session_persistence import SessionPersistence

persistence = SessionPersistence()
persistence.clear_session_cache()
```

Or delete files manually:
```
data/session_persistence/current_session.json
data/session_persistence/documents_cache.json
data/session_persistence/user_settings.json
```

### 2. Check Cache Status

```python
from session_persistence import SessionPersistence

persistence = SessionPersistence()
info = persistence.get_cache_info()

print(f"Session cached: {info['session_cached']}")
print(f"Documents cached: {info['docs_cached']}")
print(f"Document count: {info.get('docs_count', 0)}")
print(f"Saved at: {info.get('docs_saved_at', 'Never')}")
```

### 3. Manual Document Reload

If documents folder content changes but path stays the same:

```python
# Option 1: Change folder and change back (triggers reload)
# - Select different folder
# - Select original folder again

# Option 2: Clear cache and reload
from session_persistence import SessionPersistence
persistence = SessionPersistence()
persistence.save_documents_dir("NEW_PATH")  # This clears cache for new folder
```

### 4. Export Session Data

```python
import json
from session_persistence import SessionPersistence

persistence = SessionPersistence()
info = persistence.get_cache_info()

# Export to JSON for backup
with open("session_backup.json", "w") as f:
    json.dump(info, f, indent=2)
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Restore session (on startup) | < 100ms | Instant, no I/O from documents |
| Save documents cache | ~500ms - 2s | Depends on document count & size |
| Load cached documents | < 100ms | Even for 100+ documents |
| Extract topics (first time) | 2-10s | Depends on LLM/clustering |
| Extract topics (cached) | < 50ms | Instant from cache |
| Save session state | < 50ms | Happens after each interaction |

## Troubleshooting

### Issue: Cache Not Working

**Symptom**: Folder/documents not remembered on restart

**Solution**:
1. Check if `data/session_persistence/` directory exists
2. Verify file permissions on data folder
3. Clear cache: `persistence.clear_session_cache()`
4. Restart application

### Issue: Slow Startup

**Symptom**: App takes long time to start

**Solution**:
- Clear old cache if it contains many documents
- Check disk space
- Verify documents folder is accessible

### Issue: Stale Data

**Symptom**: Cached documents don't reflect changes

**Solution**:
1. Clear document cache
2. Select folder again to force reload
3. Or delete `documents_cache.json`

### Issue: Path Not Found Error

**Symptom**: Saved folder path no longer exists

**Solution**:
- Automatic: App will ask to select new folder
- Manual: Delete `user_settings.json` to reset folder selection

## Monitoring

### Enable Debug Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('session_persistence')
logger.setLevel(logging.DEBUG)
```

### Check Logs

The application logs persistence operations:

```
2026-02-20 17:40:09 - session_persistence - INFO - Cartella documenti salvata: ./documents
2026-02-20 17:40:09 - session_persistence - INFO - Cache documenti salvato: 15 documenti
2026-02-20 17:40:09 - session_persistence - INFO - Stato sessione salvato
```

## Best Practices

### 1. **Regular Backups**
- Keep backups of important conversation history
- Export `current_session.json` periodically

### 2. **Clear Cache Periodically**
- If app feels slow, clear cache
- Recommended every 1-2 weeks if heavily used

### 3. **Monitor Disk Space**
- Cache files grow with usage
- Document cache is typically the largest
- Average: 1-50MB depending on document volume

### 4. **Use Consistent Paths**
- Keep documents folder in same location
- Moving folder will require re-selection

### 5. **Handle Sensitive Data**
- Cache files store document content
- Ensure proper access controls
- Delete cache if containing sensitive data

## Security Considerations

### Data Storage

- All data stored locally in `data/session_persistence/`
- No data sent to external servers (except to configured LLM)
- File permissions inherit from directory

### Recommendations

1. **Encrypt sensitive documents** before processing
2. **Restrict folder access** to authorized users
3. **Clear cache** before leaving computer
4. **Use local LLM** if handling confidential data
5. **Backup cache** with encrypted storage

## API Reference

### SessionPersistence

```python
class SessionPersistence:
    # Save operations
    @staticmethod
    def save_documents_dir(docs_dir: str) -> None

    @staticmethod
    def save_documents(documents: List[Dict], docs_dir: str) -> None

    @staticmethod
    def save_session_state(session_state: Dict[str, Any]) -> None

    # Load operations
    @staticmethod
    def get_last_documents_dir() -> Optional[str]

    @staticmethod
    def get_cached_documents() -> Optional[Dict[str, Any]]

    @staticmethod
    def load_session_state() -> Optional[Dict[str, Any]]

    # Utility operations
    @staticmethod
    def get_cache_info() -> Dict[str, Any]

    @staticmethod
    def clear_session_cache() -> None

    @staticmethod
    def _load_settings() -> Dict[str, Any]
```

## Testing

Run the verification script to test persistence system:

```bash
python verify_session_persistence.py
```

Expected output:
- 7/7 tests passed
- All imports successful
- Directory structures verified
- Integration points validated

## Support

For issues or questions:

1. Check `verify_session_persistence.py` output
2. Review application logs (streaming to console)
3. Check `data/session_persistence/` files exist and contain data
4. Ensure write permissions on `data/` directory

---

**Version**: 1.0
**Last Updated**: 2026-02-20
**Status**: Production Ready ✓
