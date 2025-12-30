"""
Recording Session Manager

Manages recording sessions with metadata tracking,
session persistence, and organization.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
import time
import json
import shutil
import logging

logger = logging.getLogger(__name__)


@dataclass
class SessionMetadata:
    """Recording session metadata."""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0
    mouse_events: int = 0
    keyboard_events: int = 0
    screenshots: int = 0
    task_description: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    calibration_type: Optional[str] = None  # 'fitts', 'typing', 'scroll', 'free'
    quality_score: Optional[float] = None  # Automated quality assessment

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionMetadata':
        """Create from dictionary."""
        return cls(**data)


class SessionManager:
    """
    Manages recording sessions.

    Features:
        - Session lifecycle management
        - Automatic metadata tracking
        - Session organization and tagging
        - Quality assessment
        - Export and cleanup utilities
    """

    def __init__(self, base_dir: str = "recordings/sessions"):
        """
        Initialize session manager.

        Args:
            base_dir: Base directory for session storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.current_session: Optional[str] = None
        self.session_start_time: Optional[float] = None
        self._metadata_cache: Dict[str, SessionMetadata] = {}

    def start_session(
        self,
        task_description: str = "",
        tags: Optional[List[str]] = None,
        calibration_type: Optional[str] = None
    ) -> str:
        """
        Start a new recording session.

        Args:
            task_description: Description of what this session captures
            tags: Tags for categorization
            calibration_type: Type of calibration ('fitts', 'typing', 'scroll', 'free')

        Returns:
            Session ID
        """
        if self.current_session:
            logger.warning(f"Session {self.current_session} still active, ending it first")
            self.end_session()

        # Generate session ID
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_id = f"session_{timestamp}"

        # Create session directory structure
        session_dir = self.base_dir / session_id
        session_dir.mkdir()
        (session_dir / "screen_captures").mkdir()

        # Initialize metadata
        metadata = SessionMetadata(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            task_description=task_description,
            tags=tags or [],
            calibration_type=calibration_type
        )

        self._save_metadata(session_id, metadata)
        self._metadata_cache[session_id] = metadata

        self.current_session = session_id
        self.session_start_time = time.time()

        logger.info(f"Started recording session: {session_id}")

        return session_id

    def end_session(self, notes: str = "") -> Optional[SessionMetadata]:
        """
        End current recording session.

        Args:
            notes: Optional notes about the session

        Returns:
            Session metadata, or None if no active session
        """
        if not self.current_session:
            return None

        session_id = self.current_session

        # Load and update metadata
        metadata = self._load_metadata(session_id)
        if not metadata:
            logger.error(f"Could not load metadata for session {session_id}")
            return None

        metadata.end_time = datetime.now().isoformat()
        metadata.duration_seconds = time.time() - self.session_start_time
        metadata.notes = notes

        # Count events from files
        session_dir = self.base_dir / session_id

        mouse_file = session_dir / "mouse_events.jsonl"
        if mouse_file.exists():
            with open(mouse_file) as f:
                metadata.mouse_events = sum(1 for _ in f)

        keyboard_file = session_dir / "keyboard_events.jsonl"
        if keyboard_file.exists():
            with open(keyboard_file) as f:
                metadata.keyboard_events = sum(1 for _ in f)

        screenshots_dir = session_dir / "screen_captures"
        metadata.screenshots = len(list(screenshots_dir.glob("*.png")))

        # Assess quality
        metadata.quality_score = self._assess_quality(metadata)

        self._save_metadata(session_id, metadata)

        logger.info(f"Ended session {session_id}: {metadata.mouse_events} mouse, "
                   f"{metadata.keyboard_events} keyboard events, "
                   f"quality: {metadata.quality_score:.2f}")

        result = metadata
        self.current_session = None
        self.session_start_time = None

        return result

    def _assess_quality(self, metadata: SessionMetadata) -> float:
        """
        Assess session quality for profiling.

        Returns score 0-1 based on:
        - Duration (longer is better up to a point)
        - Event count (more events = better)
        - Event density (too sparse is bad)
        """
        score = 0.0

        # Duration component (0-0.3)
        # Optimal: 5-30 minutes
        duration = metadata.duration_seconds
        if duration < 30:
            score += 0.0
        elif duration < 60:
            score += 0.1
        elif duration < 300:  # 5 min
            score += 0.2
        elif duration <= 1800:  # 30 min
            score += 0.3
        else:
            score += 0.25  # Diminishing returns

        # Event count component (0-0.4)
        total_events = metadata.mouse_events + metadata.keyboard_events
        if total_events < 100:
            score += 0.0
        elif total_events < 500:
            score += 0.1
        elif total_events < 2000:
            score += 0.2
        elif total_events < 10000:
            score += 0.3
        else:
            score += 0.4

        # Event density component (0-0.3)
        if duration > 0:
            events_per_second = total_events / duration
            if events_per_second < 0.5:
                score += 0.05
            elif events_per_second < 2:
                score += 0.15
            elif events_per_second < 10:
                score += 0.3
            else:
                score += 0.2  # Too dense might indicate noise

        return min(1.0, score)

    def get_session_dir(self, session_id: Optional[str] = None) -> Optional[Path]:
        """
        Get session directory path.

        Args:
            session_id: Session ID, or None for current session

        Returns:
            Path to session directory
        """
        session_id = session_id or self.current_session
        if session_id:
            return self.base_dir / session_id
        return None

    def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """Get metadata for a specific session."""
        if session_id in self._metadata_cache:
            return self._metadata_cache[session_id]
        return self._load_metadata(session_id)

    def list_sessions(
        self,
        tags: Optional[List[str]] = None,
        calibration_type: Optional[str] = None,
        min_quality: float = 0.0
    ) -> List[SessionMetadata]:
        """
        List all recording sessions.

        Args:
            tags: Filter by tags (any match)
            calibration_type: Filter by calibration type
            min_quality: Minimum quality score

        Returns:
            List of session metadata, sorted by start time (newest first)
        """
        sessions = []

        for session_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if session_dir.is_dir() and session_dir.name.startswith('session_'):
                metadata = self._load_metadata(session_dir.name)
                if metadata:
                    # Apply filters
                    if tags and not any(t in metadata.tags for t in tags):
                        continue
                    if calibration_type and metadata.calibration_type != calibration_type:
                        continue
                    if metadata.quality_score is not None and metadata.quality_score < min_quality:
                        continue

                    sessions.append(metadata)

        return sessions

    def get_sessions_for_profiling(self, min_quality: float = 0.5) -> List[str]:
        """
        Get session paths suitable for profile generation.

        Args:
            min_quality: Minimum quality score

        Returns:
            List of session directory paths
        """
        sessions = self.list_sessions(min_quality=min_quality)
        return [str(self.base_dir / s.session_id) for s in sessions]

    def delete_session(self, session_id: str, confirm: bool = False) -> bool:
        """
        Delete a recording session.

        Args:
            session_id: Session to delete
            confirm: Must be True to actually delete

        Returns:
            True if deleted
        """
        if not confirm:
            logger.warning("Delete requires confirm=True")
            return False

        session_dir = self.base_dir / session_id

        if not session_dir.exists():
            logger.error(f"Session {session_id} not found")
            return False

        if session_id == self.current_session:
            logger.error("Cannot delete active session")
            return False

        shutil.rmtree(session_dir)
        self._metadata_cache.pop(session_id, None)

        logger.info(f"Deleted session: {session_id}")
        return True

    def add_tag(self, session_id: str, tag: str) -> None:
        """Add a tag to a session."""
        metadata = self._load_metadata(session_id)
        if metadata:
            if tag not in metadata.tags:
                metadata.tags.append(tag)
                self._save_metadata(session_id, metadata)

    def remove_tag(self, session_id: str, tag: str) -> None:
        """Remove a tag from a session."""
        metadata = self._load_metadata(session_id)
        if metadata and tag in metadata.tags:
            metadata.tags.remove(tag)
            self._save_metadata(session_id, metadata)

    def update_notes(self, session_id: str, notes: str) -> None:
        """Update session notes."""
        metadata = self._load_metadata(session_id)
        if metadata:
            metadata.notes = notes
            self._save_metadata(session_id, metadata)

    def get_total_recording_time(self) -> float:
        """Get total recording time across all sessions in seconds."""
        sessions = self.list_sessions()
        return sum(s.duration_seconds for s in sessions)

    def get_total_event_counts(self) -> Dict[str, int]:
        """Get total event counts across all sessions."""
        sessions = self.list_sessions()
        return {
            'mouse': sum(s.mouse_events for s in sessions),
            'keyboard': sum(s.keyboard_events for s in sessions),
            'screenshots': sum(s.screenshots for s in sessions)
        }

    def export_session(self, session_id: str, output_path: str) -> bool:
        """
        Export a session to a zip file.

        Args:
            session_id: Session to export
            output_path: Output zip file path

        Returns:
            True if exported successfully
        """
        session_dir = self.base_dir / session_id

        if not session_dir.exists():
            logger.error(f"Session {session_id} not found")
            return False

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.make_archive(
            str(output_path.with_suffix('')),
            'zip',
            session_dir
        )

        logger.info(f"Exported session {session_id} to {output_path}")
        return True

    def import_session(self, zip_path: str) -> Optional[str]:
        """
        Import a session from a zip file.

        Args:
            zip_path: Path to zip file

        Returns:
            Session ID if imported successfully
        """
        zip_path = Path(zip_path)

        if not zip_path.exists():
            logger.error(f"Zip file not found: {zip_path}")
            return None

        # Extract to temp location
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.unpack_archive(zip_path, temp_dir)

            # Find metadata to get session ID
            metadata_file = Path(temp_dir) / "metadata.json"
            if not metadata_file.exists():
                logger.error("No metadata.json found in archive")
                return None

            with open(metadata_file) as f:
                metadata = json.load(f)

            session_id = metadata.get('session_id')
            if not session_id:
                logger.error("No session_id in metadata")
                return None

            # Check for conflict
            if (self.base_dir / session_id).exists():
                # Generate new ID
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                session_id = f"session_{timestamp}_imported"
                metadata['session_id'] = session_id

            # Move to sessions directory
            target_dir = self.base_dir / session_id
            shutil.move(temp_dir, target_dir)

            # Update metadata file with new ID
            with open(target_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)

        logger.info(f"Imported session: {session_id}")
        return session_id

    def _save_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        """Save session metadata to file."""
        path = self.base_dir / session_id / "metadata.json"
        with open(path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
        self._metadata_cache[session_id] = metadata

    def _load_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """Load session metadata from file."""
        path = self.base_dir / session_id / "metadata.json"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    return SessionMetadata.from_dict(data)
            except Exception as e:
                logger.error(f"Error loading metadata for {session_id}: {e}")
        return None
