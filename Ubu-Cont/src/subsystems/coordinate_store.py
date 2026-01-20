"""
Coordinate Store - Persistent storage for UI element coordinates with self-healing tracking.

Stores click coordinates in JSON format with success/failure tracking to enable:
- Fast, accurate clicks using stored coordinates (no vision API calls)
- Automatic healing when consecutive failures indicate UI has changed
- Historical tracking of coordinate drift and healing events
"""

import json
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field, asdict
from threading import Lock

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CoordinateEntry:
    """Single coordinate entry with tracking metadata."""
    x: int
    y: int
    type: str  # "static" (never changes) or "dynamic" (may drift)
    description: str
    expected_x_range: Optional[Tuple[int, int]] = None
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_verified: Optional[str] = None
    last_healed: Optional[str] = None
    healing_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        # Convert expected_x_range tuple to list for JSON
        if self.expected_x_range:
            data['expected_x_range'] = list(self.expected_x_range)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoordinateEntry':
        """Create from JSON dict."""
        # Convert expected_x_range list back to tuple
        if data.get('expected_x_range'):
            data['expected_x_range'] = tuple(data['expected_x_range'])
        return cls(**data)


@dataclass
class CoordinateStats:
    """Overall statistics for coordinate tracking."""
    total_clicks: int = 0
    successful_clicks: int = 0
    failed_clicks: int = 0
    healing_events: int = 0
    last_healing: Optional[str] = None


class CoordinateStore:
    """
    Manages persistent storage of UI element coordinates with self-healing tracking.

    Thread-safe JSON-based storage with:
    - Success/failure tracking per coordinate
    - Consecutive failure counting for healing triggers
    - Healing history with before/after coordinates
    - Automatic backups before updates
    """

    def __init__(self, storage_path: str, platform: str = "instagram"):
        """
        Initialize coordinate store.

        Args:
            storage_path: Path to JSON file (relative or absolute)
            platform: Platform name (instagram, skool, facebook, etc.)
        """
        self.platform = platform

        # Convert to absolute path if relative
        if not Path(storage_path).is_absolute():
            # Relative to Ubu-Cont directory
            base_dir = Path(__file__).parent.parent.parent
            self.storage_path = base_dir / storage_path
        else:
            self.storage_path = Path(storage_path)

        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Thread safety for concurrent access
        self._lock = Lock()

        # In-memory cache
        self._coordinates: Dict[str, CoordinateEntry] = {}
        self._stats = CoordinateStats()
        self._resolution = "1600x1200"  # Default resolution

        # Load existing data
        if self.storage_path.exists():
            self._load()
            logger.info(f"Loaded {len(self._coordinates)} coordinates from {self.storage_path}")
        else:
            logger.info(f"No existing coordinate store - will create on first save")

    def exists(self) -> bool:
        """Check if coordinate store file exists."""
        return self.storage_path.exists()

    def get_coordinates(self, step_name: str) -> Optional[Tuple[int, int]]:
        """
        Get coordinates for a workflow step.

        Args:
            step_name: Name of the workflow step

        Returns:
            (x, y) tuple if found, None if not found
        """
        with self._lock:
            entry = self._coordinates.get(step_name)
            if entry:
                return (entry.x, entry.y)
            return None

    def record_success(self, step_name: str, actual_coords: Tuple[int, int]) -> None:
        """
        Record successful click at coordinates.
        Resets consecutive failure counter.

        Args:
            step_name: Name of the workflow step
            actual_coords: Coordinates that were clicked successfully
        """
        with self._lock:
            # Update entry if exists
            if step_name in self._coordinates:
                entry = self._coordinates[step_name]
                entry.success_count += 1
                entry.consecutive_failures = 0
                entry.last_verified = datetime.utcnow().isoformat() + "Z"

                # Update coordinates if they changed
                if (entry.x, entry.y) != actual_coords:
                    logger.info(f"Coordinates changed for '{step_name}': {(entry.x, entry.y)} → {actual_coords}")
                    entry.x, entry.y = actual_coords
            else:
                # Create new entry
                logger.info(f"Creating new coordinate entry for '{step_name}': {actual_coords}")
                self._coordinates[step_name] = CoordinateEntry(
                    x=actual_coords[0],
                    y=actual_coords[1],
                    type="dynamic",
                    description=f"Auto-created from successful click",
                    success_count=1,
                    last_verified=datetime.utcnow().isoformat() + "Z"
                )

            # Update global stats
            self._stats.total_clicks += 1
            self._stats.successful_clicks += 1

            # Save to disk
            self._save()

    def record_failure(self, step_name: str) -> bool:
        """
        Record failed click attempt.

        Args:
            step_name: Name of the workflow step

        Returns:
            True if healing should be triggered (>= 3 consecutive failures)
        """
        with self._lock:
            # Update entry if exists
            if step_name in self._coordinates:
                entry = self._coordinates[step_name]
                entry.failure_count += 1
                entry.consecutive_failures += 1
                logger.warning(f"Failure recorded for '{step_name}' - consecutive: {entry.consecutive_failures}")
            else:
                # Create placeholder entry
                logger.warning(f"Failure recorded for unknown step '{step_name}'")
                self._coordinates[step_name] = CoordinateEntry(
                    x=0,
                    y=0,
                    type="dynamic",
                    description="Auto-created from failure",
                    failure_count=1,
                    consecutive_failures=1
                )

            # Update global stats
            self._stats.total_clicks += 1
            self._stats.failed_clicks += 1

            # Save to disk
            self._save()

            # Check if healing needed (inline to avoid deadlock - already holding lock)
            entry = self._coordinates.get(step_name)
            if entry:
                return entry.consecutive_failures >= 3
            return False

    def should_heal(self, step_name: str) -> bool:
        """
        Check if this step needs healing (>= 3 consecutive failures).

        Args:
            step_name: Name of the workflow step

        Returns:
            True if healing should be triggered
        """
        with self._lock:
            entry = self._coordinates.get(step_name)
            if entry:
                return entry.consecutive_failures >= 3
            return False

    def get_failure_count(self, step_name: str) -> int:
        """
        Get consecutive failure count for a step.

        Args:
            step_name: Name of the workflow step

        Returns:
            Number of consecutive failures
        """
        with self._lock:
            entry = self._coordinates.get(step_name)
            if entry:
                return entry.consecutive_failures
            return 0

    def update_coordinates(
        self,
        step_name: str,
        new_coords: Tuple[int, int],
        healing_context: Dict[str, Any]
    ) -> None:
        """
        Update coordinates after healing or drift detection.
        Records healing event in history.

        Args:
            step_name: Name of the workflow step
            new_coords: New coordinates
            healing_context: Context about why/how coordinates were updated
        """
        with self._lock:
            if step_name not in self._coordinates:
                logger.error(f"Cannot update unknown step '{step_name}'")
                return

            entry = self._coordinates[step_name]
            old_coords = (entry.x, entry.y)

            # Calculate delta
            delta_x = new_coords[0] - old_coords[0]
            delta_y = new_coords[1] - old_coords[1]

            # Record healing event
            healing_event = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "old_coords": list(old_coords),
                "new_coords": list(new_coords),
                "delta": [delta_x, delta_y],
                "trigger": healing_context.get("trigger", "manual"),
                **{k: v for k, v in healing_context.items() if k != "trigger"}
            }

            entry.healing_history.append(healing_event)
            entry.x, entry.y = new_coords
            entry.last_healed = healing_event["timestamp"]
            entry.consecutive_failures = 0  # Reset after healing

            # Update global stats
            self._stats.healing_events += 1
            self._stats.last_healing = healing_event["timestamp"]

            logger.info(f"Updated coordinates for '{step_name}': {old_coords} → {new_coords} (delta: {delta_x}, {delta_y})")

            # Save to disk
            self._save()

    def add_coordinate(
        self,
        step_name: str,
        coords: Tuple[int, int],
        coord_type: str,
        description: str,
        expected_x_range: Optional[Tuple[int, int]] = None
    ) -> None:
        """
        Add a new coordinate entry (for bootstrapping).

        Args:
            step_name: Name of the workflow step
            coords: (x, y) coordinates
            coord_type: "static" or "dynamic"
            description: Human-readable description
            expected_x_range: Optional (min_x, max_x) validation range
        """
        with self._lock:
            if step_name in self._coordinates:
                logger.warning(f"Coordinate '{step_name}' already exists - skipping")
                return

            self._coordinates[step_name] = CoordinateEntry(
                x=coords[0],
                y=coords[1],
                type=coord_type,
                description=description,
                expected_x_range=expected_x_range,
                last_verified=datetime.utcnow().isoformat() + "Z"
            )

            logger.info(f"Added coordinate '{step_name}': {coords}")

            # Save to disk
            self._save()

    def get_all_steps(self) -> List[str]:
        """Get list of all stored step names."""
        with self._lock:
            return list(self._coordinates.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with self._lock:
            return {
                "total_clicks": self._stats.total_clicks,
                "successful_clicks": self._stats.successful_clicks,
                "failed_clicks": self._stats.failed_clicks,
                "healing_events": self._stats.healing_events,
                "last_healing": self._stats.last_healing,
                "success_rate": (
                    self._stats.successful_clicks / self._stats.total_clicks
                    if self._stats.total_clicks > 0 else 0.0
                )
            }

    def _load(self) -> None:
        """Load coordinates from JSON file."""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Load schema version and metadata
            schema_version = data.get("schema_version", "1.0")
            self._resolution = data.get("resolution", "1600x1200")

            # Load coordinates
            coords_data = data.get("coordinates", {})
            for step_name, coord_data in coords_data.items():
                self._coordinates[step_name] = CoordinateEntry.from_dict(coord_data)

            # Load stats
            stats_data = data.get("stats", {})
            self._stats = CoordinateStats(
                total_clicks=stats_data.get("total_clicks", 0),
                successful_clicks=stats_data.get("successful_clicks", 0),
                failed_clicks=stats_data.get("failed_clicks", 0),
                healing_events=stats_data.get("healing_events", 0),
                last_healing=stats_data.get("last_healing")
            )

            logger.info(f"Loaded coordinate store v{schema_version}")

        except Exception as e:
            logger.error(f"Failed to load coordinate store: {e}")
            # Start with empty store
            self._coordinates = {}
            self._stats = CoordinateStats()

    def _save(self) -> None:
        """Save coordinates to JSON file with backup."""
        try:
            # Create backup if file exists
            if self.storage_path.exists():
                backup_path = self.storage_path.with_suffix('.json.bak')
                shutil.copy2(self.storage_path, backup_path)

            # Build JSON structure
            data = {
                "schema_version": "1.0",
                "platform": self.platform,
                "resolution": self._resolution,
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "coordinates": {
                    step_name: entry.to_dict()
                    for step_name, entry in self._coordinates.items()
                },
                "stats": {
                    "total_clicks": self._stats.total_clicks,
                    "successful_clicks": self._stats.successful_clicks,
                    "failed_clicks": self._stats.failed_clicks,
                    "healing_events": self._stats.healing_events,
                    "last_healing": self._stats.last_healing
                }
            }

            # Write to temp file first, then rename (atomic operation)
            temp_path = self.storage_path.with_suffix('.json.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_path.replace(self.storage_path)

        except Exception as e:
            logger.error(f"Failed to save coordinate store: {e}")
