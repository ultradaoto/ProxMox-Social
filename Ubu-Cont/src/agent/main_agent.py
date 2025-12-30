"""
Main AI Computer Agent

Orchestrates all components for autonomous computer control.
"""

import time
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..capture.vnc_capturer import VNCCapturer
from ..capture.frame_buffer import ScreenStateTracker
from ..vision.omniparser import OmniParser
from ..vision.ocr import OCRProcessor
from ..vision.element_tracker import ElementTracker
from ..vision.qwen_vl import QwenVL
from ..input.human_mouse import HumanMouse, MouseConfig
from ..input.human_keyboard import HumanKeyboard, KeyboardConfig
from ..input.remote_sender import RemoteSender
from ..utils.config import Config, load_config
from ..utils.logging import setup_logging, ActionLogger

from .task_manager import TaskManager, Task
from .decision_engine import DecisionEngine
from .state_machine import StateMachine, State

logger = logging.getLogger(__name__)


@dataclass
class AgentStats:
    """Agent runtime statistics."""
    start_time: datetime = None
    actions_performed: int = 0
    tasks_completed: int = 0
    errors: int = 0
    frames_processed: int = 0
    current_state: str = "idle"


class AIComputerAgent:
    """
    Main AI agent that controls the Windows VM.

    Combines vision AI, human-like input, and decision making
    for autonomous computer operation.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize the AI agent.

        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)

        # Setup logging
        setup_logging(
            level=self.config.agent.log_level,
            log_dir='logs'
        )
        self.action_logger = ActionLogger()

        # Initialize components (lazy loaded)
        self._capturer: Optional[VNCCapturer] = None
        self._parser: Optional[OmniParser] = None
        self._ocr: Optional[OCRProcessor] = None
        self._tracker: Optional[ElementTracker] = None
        self._vlm: Optional[QwenVL] = None
        self._mouse: Optional[HumanMouse] = None
        self._keyboard: Optional[HumanKeyboard] = None
        self._sender: Optional[RemoteSender] = None

        # State management
        self._screen_tracker = ScreenStateTracker()
        self._state_machine = StateMachine()
        self._task_manager = TaskManager()
        self._decision_engine: Optional[DecisionEngine] = None

        # Runtime state
        self._running = False
        self._paused = False
        self._main_thread: Optional[threading.Thread] = None
        self.stats = AgentStats()

    def _init_components(self) -> None:
        """Initialize all components."""
        logger.info("Initializing agent components...")

        # VNC capture
        self._capturer = VNCCapturer(
            host=self.config.vnc.host,
            port=self.config.vnc.port,
            password=self.config.vnc.password,
        )

        # Vision processing
        self._parser = OmniParser(
            model_path=self.config.vision.omniparser_model,
            confidence_threshold=self.config.vision.confidence_threshold,
        )
        self._ocr = OCRProcessor(languages=[self.config.vision.ocr_lang])
        self._tracker = ElementTracker()

        # Vision-Language Model
        if self.config.vision.use_ollama:
            self._vlm = QwenVL(
                model=self.config.vision.ollama_model,
                ollama_host=self.config.vision.ollama_host,
            )

        # Remote sender
        self._sender = RemoteSender(
            host=self.config.hid.host,
            mouse_port=self.config.hid.mouse_port,
            keyboard_port=self.config.hid.keyboard_port,
        )

        # Input simulators
        mouse_config = MouseConfig(
            min_duration_ms=self.config.mouse.min_duration_ms,
            max_duration_ms=self.config.mouse.max_duration_ms,
            overshoot_probability=self.config.mouse.overshoot_probability,
            jitter_pixels=self.config.mouse.jitter_pixels,
            fitts_law_a=self.config.mouse.fitts_law_a,
            fitts_law_b=self.config.mouse.fitts_law_b,
        )
        self._mouse = HumanMouse(config=mouse_config)
        self._mouse.set_sender(self._sender)

        keyboard_config = KeyboardConfig(
            base_wpm=self.config.keyboard.base_wpm,
            wpm_variance=self.config.keyboard.wpm_variance,
            typo_rate=self.config.keyboard.typo_rate,
        )
        self._keyboard = HumanKeyboard(config=keyboard_config)
        self._keyboard.set_sender(self._sender)

        # Decision engine
        self._decision_engine = DecisionEngine(
            vlm=self._vlm,
            parser=self._parser,
            ocr=self._ocr,
        )

        logger.info("Components initialized")

    def start(self) -> None:
        """Start the AI agent."""
        if self._running:
            logger.warning("Agent already running")
            return

        logger.info("Starting AI Computer Agent")
        self.stats.start_time = datetime.now()

        try:
            self._init_components()

            # Connect to HID controller
            if not self._sender.connect():
                raise RuntimeError("Failed to connect to HID controller")

            # Connect to VNC
            if not self._capturer.connect():
                raise RuntimeError("Failed to connect to VNC server")

            self._capturer.start_capture(fps=self.config.agent.capture_fps)

            # Start main loop
            self._running = True
            self._main_thread = threading.Thread(
                target=self._main_loop,
                name='AgentMainLoop',
                daemon=True
            )
            self._main_thread.start()

            logger.info("Agent started successfully")

        except Exception as e:
            logger.error(f"Failed to start agent: {e}")
            self.stop()
            raise

    def stop(self) -> None:
        """Stop the AI agent."""
        logger.info("Stopping AI Computer Agent")
        self._running = False

        if self._capturer:
            self._capturer.stop_capture()
            self._capturer.disconnect()

        if self._sender:
            self._sender.disconnect()

        if self._main_thread and self._main_thread.is_alive():
            self._main_thread.join(timeout=5.0)

        logger.info("Agent stopped")

    def pause(self) -> None:
        """Pause agent operation."""
        self._paused = True
        self.stats.current_state = "paused"
        logger.info("Agent paused")

    def resume(self) -> None:
        """Resume agent operation."""
        self._paused = False
        logger.info("Agent resumed")

    def _main_loop(self) -> None:
        """Main agent loop."""
        logger.info("Agent main loop started")
        last_action_time = 0
        action_cooldown = self.config.timing.action_cooldown_ms / 1000

        while self._running:
            try:
                if self._paused:
                    time.sleep(0.1)
                    continue

                # Rate limiting
                elapsed = time.time() - last_action_time
                if elapsed < action_cooldown:
                    time.sleep(action_cooldown - elapsed)

                # Get latest frame
                frame = self._capturer.get_frame(timeout=1.0)
                if frame is None:
                    continue

                self.stats.frames_processed += 1

                # Update screen state tracker
                screen_stable = self._screen_tracker.update(frame)

                if not screen_stable:
                    # Wait for screen to settle after changes
                    self.stats.current_state = "waiting"
                    continue

                # Process frame through vision pipeline
                elements = self._parser.detect_elements(frame)
                tracked = self._tracker.update(elements)

                # Get current task
                current_task = self._task_manager.get_current_task()

                if current_task:
                    self.stats.current_state = "working"

                    # Decide next action
                    action = self._decision_engine.decide(
                        frame=frame,
                        elements=tracked,
                        task=current_task,
                        state=self._state_machine.current_state
                    )

                    if action:
                        # Execute action
                        success = self._execute_action(action)
                        last_action_time = time.time()

                        # Update task state
                        if action.get('task_complete'):
                            self._task_manager.complete_current()
                            self.stats.tasks_completed += 1

                else:
                    self.stats.current_state = "idle"
                    time.sleep(0.5)  # Idle wait

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.stats.errors += 1
                time.sleep(1.0)  # Back off on error

        logger.info("Agent main loop ended")

    def _execute_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute a decided action.

        Args:
            action: Action dictionary from decision engine

        Returns:
            True if action executed successfully
        """
        action_type = action.get('type')
        self.stats.actions_performed += 1

        try:
            if action_type == 'click':
                x, y = action['x'], action['y']
                self._mouse.move_to(x, y)
                self._mouse.click(button=action.get('button', 'left'))
                self.action_logger.log_click(x, y, action.get('button', 'left'))

            elif action_type == 'double_click':
                x, y = action['x'], action['y']
                self._mouse.move_to(x, y)
                self._mouse.double_click()
                self.action_logger.log_click(x, y, 'double')

            elif action_type == 'type':
                text = action['text']
                self._keyboard.type_text(text)
                self.action_logger.log_type(text, masked=action.get('sensitive', False))

            elif action_type == 'key':
                key = action['key']
                self._keyboard.press_key(key)

            elif action_type == 'hotkey':
                keys = action['keys']
                self._keyboard.hotkey(*keys)

            elif action_type == 'scroll':
                amount = action.get('amount', 100)
                direction = action.get('direction', 'down')
                self._mouse.scroll(amount, direction)
                self.action_logger.log_scroll(amount, direction)

            elif action_type == 'wait':
                duration = action.get('duration', 1.0)
                time.sleep(duration)

            elif action_type == 'move':
                x, y = action['x'], action['y']
                self._mouse.move_to(x, y)

            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to execute action {action_type}: {e}")
            return False

    def add_task(self, task: Task) -> str:
        """
        Add a task for the agent to perform.

        Args:
            task: Task to add

        Returns:
            Task ID
        """
        return self._task_manager.add_task(task)

    def add_simple_task(self, description: str, goal: str) -> str:
        """
        Add a simple task by description.

        Args:
            description: What to do
            goal: Success condition

        Returns:
            Task ID
        """
        task = Task(description=description, goal=goal)
        return self._task_manager.add_task(task)

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        uptime = None
        if self.stats.start_time:
            uptime = str(datetime.now() - self.stats.start_time)

        return {
            'running': self._running,
            'paused': self._paused,
            'uptime': uptime,
            'state': self.stats.current_state,
            'stats': {
                'actions': self.stats.actions_performed,
                'tasks_completed': self.stats.tasks_completed,
                'errors': self.stats.errors,
                'frames': self.stats.frames_processed,
            },
            'task_queue': self._task_manager.get_queue_status(),
            'connected': {
                'vnc': self._capturer.is_connected() if self._capturer else False,
                'hid': self._sender.is_connected() if self._sender else False,
            }
        }

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='AI Computer Agent')
    parser.add_argument('--config', '-c', help='Config file path')
    parser.add_argument('--task', '-t', help='Initial task to perform')
    args = parser.parse_args()

    agent = AIComputerAgent(config_path=args.config)

    try:
        agent.start()

        if args.task:
            agent.add_simple_task(
                description=args.task,
                goal="Task completed successfully"
            )

        print("\nAgent running. Press Ctrl+C to stop.")
        print(f"Status: {agent.get_status()}")

        while True:
            time.sleep(10)
            status = agent.get_status()
            print(f"\rActions: {status['stats']['actions']}, "
                  f"State: {status['state']}", end='', flush=True)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        agent.stop()


if __name__ == '__main__':
    main()
