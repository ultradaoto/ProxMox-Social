"""
Healing events tracking for real-time monitoring.
Thread-safe event store with history.
"""
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import deque
import json


@dataclass
class HealingEvent:
    """A single healing event."""
    id: str
    timestamp: str
    workflow: str
    click_index: int
    status: str  # 'started', 'ai_request', 'ai_response', 'success', 'failed'
    similarity: float = 0.0
    old_coords: Optional[tuple] = None
    new_coords: Optional[tuple] = None
    ai_confidence: float = 0.0
    ai_reasoning: str = ""
    error_message: str = ""
    duration_ms: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


class HealingEventStore:
    """
    Thread-safe store for healing events.
    Maintains history and current status.
    """
    
    def __init__(self, max_events: int = 100, max_logs: int = 200):
        self._lock = threading.Lock()
        self._events: deque = deque(maxlen=max_events)
        self._active_healings: Dict[str, HealingEvent] = {}
        self._stats = {
            'total_attempts': 0,
            'successful': 0,
            'failed': 0,
            'by_workflow': {}
        }
        self._enabled = True
        self._event_counter = 0
        self._live_logs: deque = deque(maxlen=max_logs)
        self._log_counter = 0
    
    def _gen_id(self) -> str:
        self._event_counter += 1
        return f"heal_{int(time.time())}_{self._event_counter}"
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
    
    def start_healing(self, workflow: str, click_index: int, similarity: float, old_coords: tuple) -> str:
        """Record start of a healing attempt."""
        with self._lock:
            event_id = self._gen_id()
            event = HealingEvent(
                id=event_id,
                timestamp=datetime.now().isoformat(),
                workflow=workflow,
                click_index=click_index,
                status='started',
                similarity=similarity,
                old_coords=old_coords
            )
            self._active_healings[event_id] = event
            self._events.append(event)
            self._stats['total_attempts'] += 1
            
            if workflow not in self._stats['by_workflow']:
                self._stats['by_workflow'][workflow] = {'attempts': 0, 'success': 0, 'failed': 0}
            self._stats['by_workflow'][workflow]['attempts'] += 1
            
            return event_id
    
    def update_ai_request(self, event_id: str):
        """Record AI request sent."""
        with self._lock:
            if event_id in self._active_healings:
                self._active_healings[event_id].status = 'ai_request'
    
    def update_ai_response(self, event_id: str, new_coords: tuple, confidence: float, reasoning: str):
        """Record AI response received."""
        with self._lock:
            if event_id in self._active_healings:
                event = self._active_healings[event_id]
                event.status = 'ai_response'
                event.new_coords = new_coords
                event.ai_confidence = confidence
                event.ai_reasoning = reasoning
    
    def complete_success(self, event_id: str, duration_ms: int = 0):
        """Record successful healing."""
        with self._lock:
            if event_id in self._active_healings:
                event = self._active_healings[event_id]
                event.status = 'success'
                event.duration_ms = duration_ms
                self._stats['successful'] += 1
                
                workflow = event.workflow
                if workflow in self._stats['by_workflow']:
                    self._stats['by_workflow'][workflow]['success'] += 1
                
                del self._active_healings[event_id]
    
    def complete_failed(self, event_id: str, error_message: str, duration_ms: int = 0):
        """Record failed healing."""
        with self._lock:
            if event_id in self._active_healings:
                event = self._active_healings[event_id]
                event.status = 'failed'
                event.error_message = error_message
                event.duration_ms = duration_ms
                self._stats['failed'] += 1
                
                workflow = event.workflow
                if workflow in self._stats['by_workflow']:
                    self._stats['by_workflow'][workflow]['failed'] += 1
                
                del self._active_healings[event_id]
    
    def get_events(self, limit: int = 50) -> List[dict]:
        """Get recent events."""
        with self._lock:
            events = list(self._events)[-limit:]
            return [e.to_dict() for e in reversed(events)]
    
    def get_active(self) -> List[dict]:
        """Get currently active healings."""
        with self._lock:
            return [e.to_dict() for e in self._active_healings.values()]
    
    def get_stats(self) -> dict:
        """Get overall statistics."""
        with self._lock:
            return {
                'enabled': self._enabled,
                'total_attempts': self._stats['total_attempts'],
                'successful': self._stats['successful'],
                'failed': self._stats['failed'],
                'success_rate': (self._stats['successful'] / self._stats['total_attempts'] * 100) if self._stats['total_attempts'] > 0 else 0,
                'by_workflow': dict(self._stats['by_workflow']),
                'active_count': len(self._active_healings)
            }
    
    def get_status(self) -> dict:
        """Get full status for dashboard."""
        return {
            'stats': self.get_stats(),
            'active': self.get_active(),
            'recent': self.get_events(20)
        }
    
    def clear_history(self):
        """Clear event history (keep stats)."""
        with self._lock:
            self._events.clear()
            self._live_logs.clear()
    
    def log(self, level: str, message: str, workflow: str = None, click_index: int = None):
        """Add a log entry for real-time monitoring."""
        with self._lock:
            self._log_counter += 1
            entry = {
                'id': self._log_counter,
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'message': message,
                'workflow': workflow,
                'click_index': click_index
            }
            self._live_logs.append(entry)
    
    def get_logs(self, since_id: int = 0) -> List[dict]:
        """Get log entries since a given ID."""
        with self._lock:
            return [log for log in self._live_logs if log['id'] > since_id]
    
    def get_recent_logs(self, limit: int = 50) -> List[dict]:
        """Get most recent log entries."""
        with self._lock:
            logs = list(self._live_logs)[-limit:]
            return logs


# Global singleton
_store: Optional[HealingEventStore] = None

def get_healing_store() -> HealingEventStore:
    """Get the global healing event store."""
    global _store
    if _store is None:
        _store = HealingEventStore()
    return _store
