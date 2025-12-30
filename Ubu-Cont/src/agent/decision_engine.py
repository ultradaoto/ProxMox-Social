"""
Decision Engine

Makes decisions about what actions to take based on
screen analysis, current task, and agent state.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import numpy as np

from ..vision.omniparser import UIElement
from ..vision.element_tracker import TrackedElement
from ..vision.qwen_vl import QwenVL
from ..vision.omniparser import OmniParser
from ..vision.ocr import OCRProcessor
from .task_manager import Task
from .state_machine import State

logger = logging.getLogger(__name__)


@dataclass
class ActionDecision:
    """A decided action with metadata."""
    action_type: str
    target: Optional[str]
    parameters: Dict[str, Any]
    confidence: float
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to action dictionary."""
        result = {
            'type': self.action_type,
            **self.parameters,
        }
        return result


class DecisionEngine:
    """
    Makes decisions about what actions to take.

    Uses a combination of:
    - Rule-based heuristics
    - UI element matching
    - Vision-Language model reasoning
    """

    def __init__(
        self,
        vlm: QwenVL = None,
        parser: OmniParser = None,
        ocr: OCRProcessor = None
    ):
        """
        Initialize decision engine.

        Args:
            vlm: Vision-language model for complex reasoning
            parser: UI element detector
            ocr: OCR processor
        """
        self.vlm = vlm
        self.parser = parser
        self.ocr = ocr

        self._action_history: List[Dict] = []
        self._max_history = 20

    def decide(
        self,
        frame: np.ndarray,
        elements: List[TrackedElement],
        task: Task,
        state: State
    ) -> Optional[Dict[str, Any]]:
        """
        Decide the next action to take.

        Args:
            frame: Current screen frame
            elements: Tracked UI elements
            task: Current task
            state: Current agent state

        Returns:
            Action dictionary or None if no action needed
        """
        # Try rule-based decision first (faster)
        action = self._decide_heuristic(elements, task, state)

        if action and action.confidence > 0.8:
            self._record_action(action)
            return action.to_dict()

        # Use VLM for complex decisions
        if self.vlm and self.vlm.is_available():
            action = self._decide_vlm(frame, task, state)
            if action:
                self._record_action(action)
                return action.to_dict()

        # Fallback to heuristic even with lower confidence
        if action:
            self._record_action(action)
            return action.to_dict()

        return None

    def _decide_heuristic(
        self,
        elements: List[TrackedElement],
        task: Task,
        state: State
    ) -> Optional[ActionDecision]:
        """
        Make decision using heuristic rules.

        Args:
            elements: Tracked UI elements
            task: Current task
            state: Current state

        Returns:
            ActionDecision or None
        """
        task_desc = task.description.lower()
        task_goal = task.goal.lower()

        # Look for matching elements
        for tracked in elements:
            elem = tracked.element
            elem_label = elem.label.lower()
            elem_type = elem.element_type.lower()

            # Match task keywords to elements
            if self._matches_keywords(task_desc, elem_label):
                # Found relevant element
                if elem_type in ('button', 'link', 'tab'):
                    return ActionDecision(
                        action_type='click',
                        target=elem.label,
                        parameters={
                            'x': elem.center_x,
                            'y': elem.center_y,
                        },
                        confidence=0.85 if tracked.stable else 0.6,
                        reasoning=f"Found matching {elem_type}: {elem.label}"
                    )

                elif elem_type in ('input', 'textfield', 'textarea'):
                    # Check if we need to type something
                    type_match = self._extract_type_target(task_desc)
                    if type_match:
                        return ActionDecision(
                            action_type='click',
                            target=elem.label,
                            parameters={
                                'x': elem.center_x,
                                'y': elem.center_y,
                            },
                            confidence=0.8,
                            reasoning=f"Click input field before typing"
                        )

        # Check for common actions in task
        if 'scroll' in task_desc:
            direction = 'down'
            if 'up' in task_desc:
                direction = 'up'
            return ActionDecision(
                action_type='scroll',
                target=None,
                parameters={
                    'amount': 200,
                    'direction': direction,
                },
                confidence=0.7,
                reasoning="Task mentions scrolling"
            )

        if 'wait' in task_desc:
            return ActionDecision(
                action_type='wait',
                target=None,
                parameters={'duration': 2.0},
                confidence=0.9,
                reasoning="Task mentions waiting"
            )

        return None

    def _decide_vlm(
        self,
        frame: np.ndarray,
        task: Task,
        state: State
    ) -> Optional[ActionDecision]:
        """
        Make decision using Vision-Language Model.

        Args:
            frame: Current screen frame
            task: Current task
            state: Current state

        Returns:
            ActionDecision or None
        """
        if not self.vlm:
            return None

        # Get action history for context
        history = [a['reasoning'] for a in self._action_history[-5:]]

        # Ask VLM for next action
        result = self.vlm.get_next_action(
            image=frame,
            goal=task.description,
            history=history
        )

        if result.get('action') == 'error':
            logger.warning(f"VLM error: {result.get('reasoning')}")
            return None

        action_type = result.get('action', 'wait')
        confidence = result.get('confidence', 0.5)

        # Parse VLM response into action
        if action_type == 'click':
            # Need to find the element VLM described
            target_desc = result.get('target', '')
            element = self._find_element_by_description(frame, target_desc)

            if element:
                return ActionDecision(
                    action_type='click',
                    target=target_desc,
                    parameters={
                        'x': element.center_x,
                        'y': element.center_y,
                    },
                    confidence=confidence,
                    reasoning=result.get('reasoning', 'VLM decision')
                )

        elif action_type == 'type':
            text = result.get('value', '')
            if text:
                return ActionDecision(
                    action_type='type',
                    target=None,
                    parameters={'text': text},
                    confidence=confidence,
                    reasoning=result.get('reasoning', 'VLM decision')
                )

        elif action_type == 'scroll':
            return ActionDecision(
                action_type='scroll',
                target=None,
                parameters={
                    'amount': 200,
                    'direction': 'down',
                },
                confidence=confidence,
                reasoning=result.get('reasoning', 'VLM decision')
            )

        elif action_type == 'wait':
            return ActionDecision(
                action_type='wait',
                target=None,
                parameters={'duration': 1.0},
                confidence=confidence,
                reasoning=result.get('reasoning', 'VLM decision')
            )

        elif action_type == 'done':
            return ActionDecision(
                action_type='done',
                target=None,
                parameters={'task_complete': True},
                confidence=confidence,
                reasoning=result.get('reasoning', 'Task complete')
            )

        return None

    def _find_element_by_description(
        self,
        frame: np.ndarray,
        description: str
    ) -> Optional[UIElement]:
        """
        Find an element matching a natural language description.

        Args:
            frame: Screen image
            description: Element description

        Returns:
            Matching UIElement or None
        """
        if self.vlm:
            result = self.vlm.find_element(frame, description)
            if result and result.get('found'):
                # VLM found it but we need coordinates
                # Would need to parse location or use parser
                pass

        if self.parser:
            element = self.parser.find_element_by_label(frame, description)
            if element:
                return element

        if self.ocr:
            text_region = self.ocr.find_text(frame, description)
            if text_region:
                # Convert text region to UIElement-like object
                return UIElement(
                    element_type='text',
                    label=text_region.text,
                    bbox=text_region.bbox,
                    center=text_region.center,
                    confidence=text_region.confidence,
                )

        return None

    def _matches_keywords(self, text: str, label: str) -> bool:
        """Check if label matches keywords in text."""
        # Extract meaningful words
        import re
        words = re.findall(r'\w+', text.lower())
        label_words = re.findall(r'\w+', label.lower())

        # Check for overlap
        for word in words:
            if len(word) < 3:
                continue
            for label_word in label_words:
                if word in label_word or label_word in word:
                    return True

        return False

    def _extract_type_target(self, text: str) -> Optional[str]:
        """Extract text to type from task description."""
        import re

        # Look for quoted text
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)

        # Look for "type X" pattern
        match = re.search(r'type\s+(\S+)', text, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _record_action(self, action: ActionDecision) -> None:
        """Record action in history."""
        self._action_history.append({
            'action': action.action_type,
            'target': action.target,
            'confidence': action.confidence,
            'reasoning': action.reasoning,
        })

        if len(self._action_history) > self._max_history:
            self._action_history = self._action_history[-self._max_history:]

    def get_history(self) -> List[Dict]:
        """Get action history."""
        return list(self._action_history)
