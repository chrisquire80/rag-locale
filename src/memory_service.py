import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)

# Percorso assoluto per evitare problemi con CWD diversa tra UI e API
DB_PATH = Path(__file__).parent.parent / "rag_memory.db"


class MemoryService:
    """
    Memory Service with Connection Pooling.

    Instead of opening/closing a connection for each operation,
    maintains a single persistent connection initialized once.
    This reduces overhead and improves performance.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None  # Connection pool (single persistent connection)
        self._init_db()

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up connection on exit"""
        self.close()

    def close(self):
        """Close the persistent connection"""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Memory service connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self.conn = None

    def _get_connection(self):
        """
        Get or create the persistent connection.

        Returns a single SQLite connection object that persists
        across method calls, avoiding open/close overhead.
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            logger.info(f"Memory service connection established: {self.db_path}")
        return self.conn

    def _init_db(self):
        """Initialize SQLite database with schema"""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    user_query TEXT,
                    ai_response TEXT,
                    found_anomalies BOOLEAN,
                    referenced_docs TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS action_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    level TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME,
                    completed_at DATETIME,
                    source_forecast TEXT
                )
            ''')
            conn.commit()
            logger.info(f"Memory DB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to init memory DB: {e}")

    def save_interaction(self, user_query: str, ai_response: str, found_anomalies: bool = False, referenced_docs: List[str] = None):
        """Save a Q&A interaction to memory"""
        if referenced_docs is None:
            referenced_docs = []

        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chat_history (timestamp, user_query, ai_response, found_anomalies, referenced_docs)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                user_query,
                ai_response,
                found_anomalies,
                json.dumps(referenced_docs)
            ))
            conn.commit()
            logger.info("Interaction saved to memory.")
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")

    def get_recent_memories(self, limit: int = 5) -> str:
        """Retrieve recent interactions formatted as text context"""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, user_query, ai_response, found_anomalies
                FROM chat_history
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

            if not rows:
                return ""

            context_parts = []
            for row in reversed(rows):  # Older first
                ts, q, a, anomaly = row
                marker = "[ANOMALIA]" if anomaly else ""
                context_parts.append(f"[{ts}] User: {q}\nAI: {marker} {a[:200]}...")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return ""

    def search_memories(self, query: str, limit: int = 3) -> str:
        """Simple keyword search for memory recall."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, user_query, ai_response
                FROM chat_history
                WHERE user_query LIKE ? OR ai_response LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (f'%{query}%', f'%{query}%', limit))
            rows = cursor.fetchall()
            conn.close()

            context_parts = []
            for row in rows:
                ts, q, a = row
                context_parts.append(f"[{ts}] (Recall) User: {q}\nAI: {a[:200]}...")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return ""

    def get_anomalies_history(self, limit: int = 20) -> List[Dict]:
        """Retrieve recent interactions where anomalies were found (structured)."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, user_query, ai_response, referenced_docs
                FROM chat_history
                WHERE found_anomalies = 1
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [
                {"id": r[0], "timestamp": r[1], "user_query": r[2], "ai_response": r[3], "referenced_docs": r[4]}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve anomaly history: {e}")
            return []

    def get_all_interactions_for_forecast(self, limit: int = 30) -> List[Dict]:
        """
        Retrieve recent interactions for Predictive Forecasting.
        Returns structured rows with timestamp, query, anomaly flag, and referenced docs.
        """
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, user_query, ai_response, found_anomalies, referenced_docs
                FROM chat_history
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "timestamp": r[0],
                    "user_query": r[1],
                    "ai_response": r[2][:300],
                    "found_anomalies": bool(r[3]),
                    "referenced_docs": r[4]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve interactions for forecast: {e}")
            return []

    def get_stats(self) -> Dict:
        """Get summary statistics of the memory database."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(found_anomalies) FROM chat_history")
            total, anomalies = cursor.fetchone()
            conn.close()
            return {
                "total_interactions": total or 0,
                "total_anomalies": int(anomalies or 0),
                "anomaly_rate": (anomalies / total) if total else 0.0,
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"total_interactions": 0, "total_anomalies": 0, "anomaly_rate": 0.0}

    # ── Task Board CRUD ───────────────────────────────────────────────────

    def add_task(self, title: str, level: str, source: str = ""):
        """Add a new task to the persistent checklist."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO action_tasks (title, level, created_at, source_forecast)
                VALUES (?, ?, ?, ?)
            ''', (title, level, datetime.now(), source))
            conn.commit()
            conn.close()
            logger.info(f"Task added: {title}")
        except Exception as e:
            logger.error(f"Failed to add task: {e}")

    def get_all_tasks(self) -> List[Dict]:
        """List all tasks sorted by urgency."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, level, status, created_at, completed_at
                FROM action_tasks
                ORDER BY CASE 
                    WHEN level = 'URGENTE' THEN 1
                    WHEN level = 'PREVENTIVO' THEN 2
                    ELSE 3 
                END ASC, created_at DESC
            ''')
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0], "title": r[1], "level": r[2], 
                    "status": r[3], "created_at": r[4], "completed_at": r[5]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []

    def toggle_task(self, task_id: int):
        """Toggle task status between pending and completed."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            # Check current status
            cursor.execute("SELECT status FROM action_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return

            new_status = "completed" if row[0] == "pending" else "pending"
            comp_at = datetime.now() if new_status == "completed" else None

            cursor.execute('''
                UPDATE action_tasks 
                SET status = ?, completed_at = ?
                WHERE id = ?
            ''', (new_status, comp_at, task_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to toggle task: {e}")

    def delete_task(self, task_id: int):
        """Delete a task."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute("DELETE FROM action_tasks WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")

    def get_task_completion_rate(self) -> float:
        """Calculate percentage of completed tasks."""
        try:
            conn = self._get_connection()  # Use pooled connection
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) FROM action_tasks")
            total, completed = cursor.fetchone()
            conn.close()
            if not total:
                return 0.0
            return (completed or 0) / total
        except Exception as e:
            logger.error(f"Failed to get completion rate: {e}")
            return 0.0


# Singleton
_memory_service = None


def get_memory_service():
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
