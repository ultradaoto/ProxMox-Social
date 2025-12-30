"""
State Machine

Tracks workflow state for complex multi-step tasks.
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


class StateType(Enum):
    """Types of states."""
    INITIAL = auto()
    INTERMEDIATE = auto()
    FINAL = auto()
    ERROR = auto()


@dataclass
class State:
    """A workflow state."""
    name: str
    state_type: StateType = StateType.INTERMEDIATE
    data: Dict[str, Any] = field(default_factory=dict)
    entered_at: datetime = None
    exit_conditions: List[str] = field(default_factory=list)

    def __str__(self):
        return self.name


@dataclass
class Transition:
    """A state transition."""
    from_state: str
    to_state: str
    condition: str  # Description of transition condition
    action: Optional[str] = None  # Action to take on transition


class StateMachine:
    """
    Tracks workflow state for complex tasks.

    Supports:
    - Named states with entry/exit tracking
    - Condition-based transitions
    - State history
    - Error state handling
    """

    def __init__(self):
        self._states: Dict[str, State] = {}
        self._transitions: List[Transition] = []
        self._current: Optional[State] = None
        self._history: List[tuple] = []  # (state_name, entered_at, exited_at)

        # Create default states
        self._add_default_states()

    def _add_default_states(self) -> None:
        """Add default states."""
        self.add_state(State(
            name='idle',
            state_type=StateType.INITIAL,
        ))
        self.add_state(State(
            name='working',
            state_type=StateType.INTERMEDIATE,
        ))
        self.add_state(State(
            name='waiting',
            state_type=StateType.INTERMEDIATE,
        ))
        self.add_state(State(
            name='completed',
            state_type=StateType.FINAL,
        ))
        self.add_state(State(
            name='error',
            state_type=StateType.ERROR,
        ))

        # Set initial state
        self._current = self._states['idle']
        self._current.entered_at = datetime.now()

    def add_state(self, state: State) -> None:
        """Add a new state."""
        self._states[state.name] = state

    def add_transition(
        self,
        from_state: str,
        to_state: str,
        condition: str,
        action: str = None
    ) -> None:
        """Add a transition between states."""
        self._transitions.append(Transition(
            from_state=from_state,
            to_state=to_state,
            condition=condition,
            action=action,
        ))

    @property
    def current_state(self) -> State:
        """Get current state."""
        return self._current

    @property
    def state_name(self) -> str:
        """Get current state name."""
        return self._current.name if self._current else 'unknown'

    def transition_to(self, state_name: str, reason: str = None) -> bool:
        """
        Transition to a new state.

        Args:
            state_name: Target state name
            reason: Reason for transition

        Returns:
            True if transition successful
        """
        if state_name not in self._states:
            logger.warning(f"Unknown state: {state_name}")
            return False

        old_state = self._current
        new_state = self._states[state_name]

        # Record exit
        if old_state:
            self._history.append((
                old_state.name,
                old_state.entered_at,
                datetime.now()
            ))
            logger.debug(f"Exiting state: {old_state.name}")

        # Enter new state
        new_state.entered_at = datetime.now()
        self._current = new_state
        logger.info(f"Transitioned to state: {state_name}"
                   + (f" ({reason})" if reason else ""))

        return True

    def is_in_state(self, state_name: str) -> bool:
        """Check if currently in a specific state."""
        return self._current and self._current.name == state_name

    def is_final(self) -> bool:
        """Check if in a final state."""
        return self._current and self._current.state_type == StateType.FINAL

    def is_error(self) -> bool:
        """Check if in error state."""
        return self._current and self._current.state_type == StateType.ERROR

    def set_state_data(self, key: str, value: Any) -> None:
        """Set data on current state."""
        if self._current:
            self._current.data[key] = value

    def get_state_data(self, key: str, default: Any = None) -> Any:
        """Get data from current state."""
        if self._current:
            return self._current.data.get(key, default)
        return default

    def time_in_state(self) -> float:
        """Get seconds in current state."""
        if self._current and self._current.entered_at:
            return (datetime.now() - self._current.entered_at).total_seconds()
        return 0.0

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get state history."""
        history = []
        for name, entered, exited in self._history[-limit:]:
            history.append({
                'state': name,
                'entered': entered.isoformat() if entered else None,
                'exited': exited.isoformat() if exited else None,
                'duration': (exited - entered).total_seconds() if entered and exited else None,
            })
        return history

    def reset(self) -> None:
        """Reset to initial state."""
        self._history.clear()
        self._current = self._states.get('idle')
        if self._current:
            self._current.entered_at = datetime.now()
            self._current.data.clear()


class WorkflowStateMachine(StateMachine):
    """
    Extended state machine for common workflows.

    Provides pre-built states and transitions for
    common automation scenarios.
    """

    def __init__(self, workflow_type: str = 'generic'):
        super().__init__()
        self._workflow_type = workflow_type
        self._setup_workflow(workflow_type)

    def _setup_workflow(self, workflow_type: str) -> None:
        """Set up workflow-specific states and transitions."""
        if workflow_type == 'login':
            self._setup_login_workflow()
        elif workflow_type == 'form_fill':
            self._setup_form_workflow()
        elif workflow_type == 'navigation':
            self._setup_navigation_workflow()

    def _setup_login_workflow(self) -> None:
        """Set up login workflow."""
        self.add_state(State(name='finding_login_form'))
        self.add_state(State(name='entering_username'))
        self.add_state(State(name='entering_password'))
        self.add_state(State(name='clicking_submit'))
        self.add_state(State(name='verifying_login'))

        self.add_transition('idle', 'finding_login_form', 'Login task started')
        self.add_transition('finding_login_form', 'entering_username', 'Found login form')
        self.add_transition('entering_username', 'entering_password', 'Username entered')
        self.add_transition('entering_password', 'clicking_submit', 'Password entered')
        self.add_transition('clicking_submit', 'verifying_login', 'Submit clicked')
        self.add_transition('verifying_login', 'completed', 'Login successful')
        self.add_transition('verifying_login', 'error', 'Login failed')

    def _setup_form_workflow(self) -> None:
        """Set up form filling workflow."""
        self.add_state(State(name='finding_form'))
        self.add_state(State(name='filling_fields'))
        self.add_state(State(name='reviewing'))
        self.add_state(State(name='submitting'))

        self.add_transition('idle', 'finding_form', 'Form task started')
        self.add_transition('finding_form', 'filling_fields', 'Found form')
        self.add_transition('filling_fields', 'reviewing', 'All fields filled')
        self.add_transition('reviewing', 'submitting', 'Form reviewed')
        self.add_transition('submitting', 'completed', 'Form submitted')

    def _setup_navigation_workflow(self) -> None:
        """Set up navigation workflow."""
        self.add_state(State(name='starting'))
        self.add_state(State(name='navigating'))
        self.add_state(State(name='arrived'))

        self.add_transition('idle', 'starting', 'Navigation started')
        self.add_transition('starting', 'navigating', 'Target identified')
        self.add_transition('navigating', 'arrived', 'Reached destination')
        self.add_transition('arrived', 'completed', 'Navigation complete')
