# 🎨 RAG LOCALE Dashboard - User Guide

**Version**: 2.0 Production Edition
**Date**: February 20, 2026
**Status**: ✅ PRODUCTION READY

---

## Quick Start

### 1. Install Streamlit (if not already installed)
```bash
pip install streamlit
```

### 2. Run the Dashboard
```bash
streamlit run app_dashboard.py
```

The dashboard will open in your browser at `http://localhost:8501`

---

## Dashboard Features

### 📊 Tab 1: System Status
Real-time overview of the entire RAG LOCALE system:
- **Documents Loaded**: Shows total indexed documents (971)
- **Vector Store Size**: Current storage size (27.8 MB)
- **Hardware Status**: CPU cores and RAM available
- **System Status**: Overall operational status
- **Hardware Configuration**: Detailed CPU, memory, platform info
- **Optimization Status**: Current optimization settings
- **Full Optimization Report**: Comprehensive system profile

**Use Case**: Check system health at a glance

---

### ⚡ Tab 2: Performance Metrics
Monitor real-time performance statistics:
- **Operation Timing**: Min/max/mean timing for all operations
- **Metrics Summary**: Quick view of top operations
- **Expected Performance**: Baseline performance targets
  - Query Cached: 10ms (20x faster)
  - Vector Search: 50-100ms (for 971 documents)
  - Async Queries: 2-3x faster than sequential

**Use Case**: Identify performance bottlenecks and trends

---

### 💾 Tab 3: Resource Monitor
Real-time system resource monitoring:
- **Memory Usage**: Current RAM usage percentage and available memory
- **CPU Usage**: CPU utilization and core count
- **System Health Score**: Overall system health (0-100)
- **Resource Timeline**: Historical data (live monitoring)
- **System Recommendations**: Automatic suggestions based on current load

**Color Coding**:
- 🟢 Green: Healthy (< 70%)
- 🟡 Yellow: Elevated (70-80%)
- 🔴 Red: Critical (> 80%)

**Use Case**: Monitor system resources during heavy workloads

---

### 🔧 Tab 4: Optimizations
View all active and available optimizations:
- **Enabled Optimizations**:
  - Async Query Processing (2-3x faster)
  - Performance Profiling (<1% overhead)
  - Hardware Auto-Tuning (automatic)
  - HNSW Vector Search (10-100x for 1000+ docs)
  - Query Caching (2-hour TTL)
  - Multi-threaded PDF Processing (4-8x faster)

- **Available Features**:
  - INT8 Quantization (75% memory reduction)
  - HNSW Indexing (sub-millisecond search)
  - Async I/O (non-blocking)
  - Multi-threading (parallel processing)
  - Memory Management (automatic)
  - Error Recovery (graceful degradation)

- **Performance Improvements**: Visual display of all speedups

**Use Case**: Understand what optimizations are active and available

---

### 💬 Tab 5: Query Interface
Interactive query interface with performance tracking:
- **Query Input**: Enter your question
- **Auto-approve Option**: Skip HITL validation if confident
- **Response Display**: View the generated answer
- **Metrics**: Query execution time, sources used, model info
- **Sources**: Expandable source references
- **Query Statistics**: Overall document and search stats

**Example Queries**:
- "What is ETICA?"
- "How does the HR system work?"
- "Describe the smart working policy"

**Use Case**: Direct interaction with the RAG system with monitoring

---

## Understanding the Metrics

### Response Time
- **< 50ms**: Excellent (cached query)
- **50-200ms**: Good (normal search)
- **200-500ms**: Acceptable (complex query)
- **> 500ms**: Check hardware and optimization status

### Memory Usage
- **< 50%**: Optimal
- **50-70%**: Good
- **70-80%**: Monitor
- **> 80%**: Take action (close apps, enable quantization)

### CPU Usage
- **< 30%**: Idle
- **30-60%**: Normal operations
- **60-80%**: Active processing
- **> 80%**: High load (parallel processing active)

---

## Tips for Best Performance

1. **Monitor Memory**: Keep below 70% for optimal performance
2. **Use Async Queries**: For batch processing, use async mode (2-3x faster)
3. **Enable Caching**: Query caching provides 20x speedup for repeated queries
4. **Check Hardware**: Verify optimization is active via System Status tab
5. **Review Metrics**: Use Performance Metrics to identify slow operations

---

## Troubleshooting

### Dashboard Won't Start
```bash
# Check Streamlit installation
pip show streamlit

# Reinstall if needed
pip install --upgrade streamlit
```

### High Memory Usage
1. Check "Resource Monitor" tab
2. If > 80%, enable INT8 quantization in code
3. Close other applications
4. Reduce max_parallel_workers

### Slow Queries
1. Check "Performance Metrics" tab
2. Look for high-latency operations
3. Verify HNSW is enabled (for 100+ docs)
4. Check if memory is constrained

### Connection Issues
1. Ensure app_dashboard.py is in project root
2. Run from correct directory: `cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE`
3. Check port 8501 is not in use: `netstat -ano | findstr :8501`

---

## Advanced Configuration

### Change Refresh Interval
In Tab 3 (Resource Monitor), use the slider to adjust how often metrics update:
- **1-3 seconds**: High frequency (uses more CPU)
- **4-6 seconds**: Normal (balanced)
- **7-10 seconds**: Low frequency (minimal overhead)

### Customize Auto-Approval
In Tab 5 (Query Interface), toggle "Auto-approve" to:
- **Checked**: Skip HITL validation (faster, use for testing)
- **Unchecked**: Full HITL validation (production recommended)

---

## Performance Baseline

### System Configuration
- **Hardware**: 14 cores, 15.5GB RAM
- **Documents**: 971 indexed
- **Vector Store**: 27.8 MB
- **Python**: 3.14.0

### Expected Baseline
- **Startup**: 2-3 seconds
- **Dashboard Load**: 1-2 seconds
- **Query Response**: 50-100ms
- **Metrics Update**: Real-time (< 100ms)

---

## Features in Development

Future enhancements:
- ⏳ Historical performance graphs
- ⏳ Query history and trending
- ⏳ Advanced filtering and search
- ⏳ Export metrics to CSV/JSON
- ⏳ Custom alerts and thresholds
- ⏳ Multi-user session management

---

## Support & Documentation

For more information, see:
- **Integration Guide**: `INTEGRATION_GUIDE.md`
- **Usage Guide**: `USAGE_GUIDE_OPTIMIZATIONS.md`
- **Technical Details**: `PERFORMANCE_OPTIMIZATION_COMPLETE.md`
- **Deployment Report**: `DEPLOYMENT_REPORT.txt`

---

## Version History

### v2.0 (February 20, 2026)
- ✅ Complete frontend redesign
- ✅ 5-tab dashboard interface
- ✅ Real-time resource monitoring
- ✅ Performance metrics visualization
- ✅ Optimization status display
- ✅ Interactive query interface

### v1.0 (February 15, 2026)
- Initial implementation

---

**Status**: ✅ PRODUCTION READY

The dashboard is ready for production use with all optimization features integrated and monitored in real-time.

