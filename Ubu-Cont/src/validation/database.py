"""
SQLite database operations for workflow validation.
"""
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class ValidationDatabase:
    """Manages SQLite database for workflow validation."""
    
    def __init__(self, db_path: str):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_schema(self) -> None:
        """Initialize database schema if not exists."""
        schema = '''
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            json_path TEXT NOT NULL,
            platform TEXT NOT NULL,
            total_actions INTEGER NOT NULL,
            click_count INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS click_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            action_index INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            click_x INTEGER NOT NULL,
            click_y INTEGER NOT NULL,
            baseline_image BLOB NOT NULL,
            image_hash TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confidence_threshold REAL DEFAULT 0.95,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id),
            UNIQUE(workflow_id, action_index)
        );

        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            post_id TEXT,
            status TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            failure_action_index INTEGER,
            failure_reason TEXT,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE TABLE IF NOT EXISTS run_screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            action_index INTEGER NOT NULL,
            click_x INTEGER NOT NULL,
            click_y INTEGER NOT NULL,
            captured_image BLOB NOT NULL,
            image_hash TEXT NOT NULL,
            baseline_match_score REAL,
            is_match BOOLEAN,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES workflow_runs(id)
        );

        CREATE TABLE IF NOT EXISTS workflow_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            action_index INTEGER NOT NULL,
            old_click_x INTEGER NOT NULL,
            old_click_y INTEGER NOT NULL,
            new_click_x INTEGER NOT NULL,
            new_click_y INTEGER NOT NULL,
            old_baseline_image BLOB,
            new_baseline_image BLOB,
            reason TEXT,
            consecutive_failures INTEGER,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE INDEX IF NOT EXISTS idx_baselines_workflow ON click_baselines(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_runs_workflow ON workflow_runs(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status);
        CREATE INDEX IF NOT EXISTS idx_screenshots_run ON run_screenshots(run_id);
        CREATE INDEX IF NOT EXISTS idx_corrections_workflow ON workflow_corrections(workflow_id);
        '''
        with self._get_connection() as conn:
            conn.executescript(schema)
    
    def register_workflow(
        self,
        name: str,
        json_path: str,
        platform: str,
        total_actions: int,
        click_count: int
    ) -> int:
        """Register a new workflow or update existing. Returns Workflow ID."""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO workflows (name, json_path, platform, total_actions, click_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    json_path = excluded.json_path,
                    total_actions = excluded.total_actions,
                    click_count = excluded.click_count,
                    updated_at = CURRENT_TIMESTAMP
            ''', (name, json_path, platform, total_actions, click_count))
            
            row = conn.execute('SELECT id FROM workflows WHERE name = ?', (name,)).fetchone()
            return row[0]
    
    def get_workflow(self, name: str) -> Optional[Dict]:
        """Get workflow by name."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM workflows WHERE name = ?', (name,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_workflow_by_id(self, workflow_id: int) -> Optional[Dict]:
        """Get workflow by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM workflows WHERE id = ?', (workflow_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def save_baseline(
        self,
        workflow_id: int,
        action_index: int,
        action_type: str,
        click_x: int,
        click_y: int,
        image_data: bytes,
        description: str = None,
        threshold: float = 0.95
    ) -> int:
        """Save or update a baseline image for a click action. Returns Baseline ID."""
        image_hash = hashlib.sha256(image_data).hexdigest()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO click_baselines 
                    (workflow_id, action_index, action_type, click_x, click_y, 
                     baseline_image, image_hash, description, confidence_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id, action_index) DO UPDATE SET
                    action_type = excluded.action_type,
                    click_x = excluded.click_x,
                    click_y = excluded.click_y,
                    baseline_image = excluded.baseline_image,
                    image_hash = excluded.image_hash,
                    description = excluded.description,
                    confidence_threshold = excluded.confidence_threshold
            ''', (workflow_id, action_index, action_type, click_x, click_y,
                  image_data, image_hash, description, threshold))
            
            row = conn.execute(
                'SELECT id FROM click_baselines WHERE workflow_id = ? AND action_index = ?',
                (workflow_id, action_index)
            ).fetchone()
            return row[0]
    
    def get_baselines(self, workflow_id: int) -> List[Dict]:
        """Get all baselines for a workflow."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM click_baselines 
                WHERE workflow_id = ? 
                ORDER BY action_index
            ''', (workflow_id,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_baseline(self, workflow_id: int, action_index: int) -> Optional[Dict]:
        """Get specific baseline."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM click_baselines 
                WHERE workflow_id = ? AND action_index = ?
            ''', (workflow_id, action_index)).fetchone()
            return dict(row) if row else None
    
    def start_run(self, workflow_id: int, post_id: str = None) -> int:
        """Start tracking a new workflow run. Returns Run ID."""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO workflow_runs (workflow_id, post_id, status)
                VALUES (?, ?, 'running')
            ''', (workflow_id, post_id))
            return cursor.lastrowid
    
    def save_run_screenshot(
        self,
        run_id: int,
        action_index: int,
        click_x: int,
        click_y: int,
        image_data: bytes,
        match_score: float = None,
        is_match: bool = None
    ) -> int:
        """Save screenshot captured during run."""
        image_hash = hashlib.sha256(image_data).hexdigest()
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO run_screenshots 
                    (run_id, action_index, click_x, click_y, 
                     captured_image, image_hash, baseline_match_score, is_match)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (run_id, action_index, click_x, click_y,
                  image_data, image_hash, match_score, is_match))
            return cursor.lastrowid
    
    def update_run_screenshot(
        self,
        run_id: int,
        action_index: int,
        match_score: float,
        is_match: bool
    ) -> None:
        """Update screenshot with match results."""
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE run_screenshots SET
                    baseline_match_score = ?,
                    is_match = ?
                WHERE run_id = ? AND action_index = ?
            ''', (match_score, is_match, run_id, action_index))
    
    def complete_run(
        self,
        run_id: int,
        status: str,
        failure_index: int = None,
        failure_reason: str = None
    ) -> None:
        """Mark a run as complete."""
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE workflow_runs SET
                    status = ?,
                    completed_at = CURRENT_TIMESTAMP,
                    failure_action_index = ?,
                    failure_reason = ?
                WHERE id = ?
            ''', (status, failure_index, failure_reason, run_id))
    
    def get_recent_runs(self, workflow_id: int, limit: int = 10) -> List[Dict]:
        """Get recent runs for a workflow."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM workflow_runs
                WHERE workflow_id = ?
                ORDER BY started_at DESC
                LIMIT ?
            ''', (workflow_id, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def count_consecutive_failures(
        self,
        workflow_id: int,
        action_index: int
    ) -> int:
        """Count consecutive failures at a specific action."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT status, failure_action_index FROM workflow_runs
                WHERE workflow_id = ?
                ORDER BY completed_at DESC
                LIMIT 10
            ''', (workflow_id,)).fetchall()
            
            count = 0
            for row in rows:
                if row['status'] == 'validation_failed' and row['failure_action_index'] == action_index:
                    count += 1
                else:
                    break
            return count
    
    def get_run_screenshots(self, run_id: int) -> List[Dict]:
        """Get all screenshots for a run."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM run_screenshots
                WHERE run_id = ?
                ORDER BY action_index
            ''', (run_id,)).fetchall()
            return [dict(row) for row in rows]
