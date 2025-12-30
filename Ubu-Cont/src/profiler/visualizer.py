"""
Profile Visualizer

Visualizes behavioral patterns from recordings and profiles.
Useful for understanding and validating captured patterns.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import math
import logging

logger = logging.getLogger(__name__)

# Try to import visualization libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.collections import LineCollection
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not available, visualization disabled")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class ProfileVisualizer:
    """
    Visualizes behavioral patterns and profiles.

    Features:
        - Mouse trajectory visualization
        - Velocity profiles
        - Keyboard timing heatmaps
        - Fitts's Law plots
        - Digraph timing charts
    """

    def __init__(self, output_dir: str = "visualizations"):
        """
        Initialize visualizer.

        Args:
            output_dir: Directory to save visualizations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not HAS_MATPLOTLIB:
            logger.warning("Matplotlib not available. Install with: pip install matplotlib")

    def plot_mouse_trajectory(
        self,
        events: List[Dict],
        title: str = "Mouse Trajectory",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> Optional[str]:
        """
        Plot mouse movement trajectories.

        Args:
            events: List of mouse events
            title: Plot title
            save_path: Path to save image
            show: Whether to display plot

        Returns:
            Path to saved image if saved
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib required for visualization")
            return None

        # Extract movement data
        move_events = [e for e in events if e.get('event_type') == 'move']
        click_events = [e for e in events if e.get('event_type') == 'click']

        if not move_events:
            logger.warning("No movement data to visualize")
            return None

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))

        # Plot trajectory
        x = [e['x'] for e in move_events]
        y = [e['y'] for e in move_events]

        # Color by velocity if available
        if move_events[0].get('velocity') is not None:
            velocities = [e.get('velocity', 0) for e in move_events]

            if HAS_NUMPY:
                points = np.array([x, y]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)

                norm = plt.Normalize(min(velocities), max(velocities))
                lc = LineCollection(segments, cmap='viridis', norm=norm)
                lc.set_array(np.array(velocities[:-1]))
                lc.set_linewidth(2)
                line = ax.add_collection(lc)
                fig.colorbar(line, ax=ax, label='Velocity (px/s)')
            else:
                ax.plot(x, y, 'b-', linewidth=1, alpha=0.7)
        else:
            ax.plot(x, y, 'b-', linewidth=1, alpha=0.7)

        # Mark clicks
        for event in click_events:
            if event.get('pressed'):
                color = 'red' if event.get('button') == 'left' else 'green'
                ax.plot(event['x'], event['y'], 'o', color=color, markersize=8)

        # Invert y-axis (screen coordinates)
        ax.invert_yaxis()

        ax.set_xlabel('X Position (pixels)')
        ax.set_ylabel('Y Position (pixels)')
        ax.set_title(title)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # Save if requested
        saved_path = None
        if save_path:
            saved_path = save_path
        else:
            saved_path = str(self.output_dir / f"trajectory_{int(move_events[0].get('timestamp', 0))}.png")

        plt.savefig(saved_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved trajectory plot to {saved_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return saved_path

    def plot_velocity_profile(
        self,
        events: List[Dict],
        title: str = "Velocity Profile",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> Optional[str]:
        """
        Plot velocity over time for movements.

        Args:
            events: List of mouse events
            title: Plot title
            save_path: Path to save image
            show: Whether to display

        Returns:
            Path to saved image
        """
        if not HAS_MATPLOTLIB:
            return None

        move_events = [e for e in events if e.get('event_type') == 'move' and e.get('velocity')]

        if not move_events:
            logger.warning("No velocity data to visualize")
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        timestamps = [e['timestamp'] - move_events[0]['timestamp'] for e in move_events]
        velocities = [e['velocity'] for e in move_events]

        ax.plot(timestamps, velocities, 'b-', linewidth=1)
        ax.fill_between(timestamps, velocities, alpha=0.3)

        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Velocity (pixels/second)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

        # Save
        saved_path = save_path or str(self.output_dir / f"velocity_{int(move_events[0]['timestamp'])}.png")
        plt.savefig(saved_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return saved_path

    def plot_fitts_law(
        self,
        movements: List[Dict],
        profile: Optional[Dict] = None,
        title: str = "Fitts's Law Analysis",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> Optional[str]:
        """
        Plot Fitts's Law analysis.

        Args:
            movements: List of movement data with distance, time, target_width
            profile: Optional profile with Fitts coefficients
            title: Plot title
            save_path: Path to save image
            show: Whether to display

        Returns:
            Path to saved image
        """
        if not HAS_MATPLOTLIB or not HAS_NUMPY:
            return None

        # Calculate index of difficulty
        id_values = []
        times = []

        for m in movements:
            d = m.get('distance', 0)
            w = m.get('target_width', 20)
            t = m.get('duration', 0) * 1000  # Convert to ms

            if d > 10 and t > 0 and w > 0:
                id_val = math.log2(d / w + 1)
                id_values.append(id_val)
                times.append(t)

        if len(id_values) < 5:
            logger.warning("Not enough data for Fitts's Law plot")
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        # Scatter plot of actual data
        ax.scatter(id_values, times, alpha=0.5, label='Actual movements')

        # Fit line
        id_arr = np.array(id_values)
        times_arr = np.array(times)

        # Linear regression
        coeffs = np.polyfit(id_arr, times_arr, 1)
        fit_line = np.poly1d(coeffs)

        x_range = np.linspace(min(id_values), max(id_values), 100)
        ax.plot(x_range, fit_line(x_range), 'r-', linewidth=2,
               label=f'Fit: T = {coeffs[1]:.1f} + {coeffs[0]:.1f} × ID')

        # Add profile line if provided
        if profile:
            fitts = profile.get('mouse', {}).get('fitts_law', {})
            a = fitts.get('a', 0)
            b = fitts.get('b', 0)
            if a and b:
                profile_line = a + b * x_range
                ax.plot(x_range, profile_line, 'g--', linewidth=2,
                       label=f'Profile: T = {a:.1f} + {b:.1f} × ID')

        ax.set_xlabel('Index of Difficulty (bits)')
        ax.set_ylabel('Movement Time (ms)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Calculate R²
        ss_res = np.sum((times_arr - fit_line(id_arr))**2)
        ss_tot = np.sum((times_arr - np.mean(times_arr))**2)
        r2 = 1 - (ss_res / ss_tot)
        ax.text(0.05, 0.95, f'R² = {r2:.3f}', transform=ax.transAxes,
               verticalalignment='top')

        saved_path = save_path or str(self.output_dir / "fitts_law.png")
        plt.savefig(saved_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return saved_path

    def plot_typing_rhythm(
        self,
        events: List[Dict],
        title: str = "Typing Rhythm",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> Optional[str]:
        """
        Plot keyboard typing rhythm.

        Args:
            events: List of keyboard events
            title: Plot title
            save_path: Path to save
            show: Whether to display

        Returns:
            Path to saved image
        """
        if not HAS_MATPLOTLIB:
            return None

        press_events = [e for e in events if e.get('event_type') == 'press']

        if len(press_events) < 10:
            logger.warning("Not enough typing data")
            return None

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # Inter-key intervals over time
        ikis = []
        times = []
        for i, event in enumerate(press_events):
            iki = event.get('inter_key_interval')
            if iki and iki < 2000:
                ikis.append(iki)
                times.append(event['timestamp'] - press_events[0]['timestamp'])

        axes[0].plot(times, ikis, 'b-', linewidth=0.5, alpha=0.7)
        axes[0].scatter(times, ikis, s=5, alpha=0.5)
        axes[0].set_xlabel('Time (seconds)')
        axes[0].set_ylabel('Inter-Key Interval (ms)')
        axes[0].set_title('Typing Rhythm Over Time')
        axes[0].grid(True, alpha=0.3)

        # IKI histogram
        if HAS_NUMPY:
            axes[1].hist(ikis, bins=50, density=True, alpha=0.7)
            axes[1].axvline(np.mean(ikis), color='r', linestyle='--',
                           label=f'Mean: {np.mean(ikis):.1f}ms')
            axes[1].axvline(np.median(ikis), color='g', linestyle='--',
                           label=f'Median: {np.median(ikis):.1f}ms')
        else:
            axes[1].hist(ikis, bins=50, density=True, alpha=0.7)

        axes[1].set_xlabel('Inter-Key Interval (ms)')
        axes[1].set_ylabel('Density')
        axes[1].set_title('IKI Distribution')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        saved_path = save_path or str(self.output_dir / "typing_rhythm.png")
        plt.savefig(saved_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return saved_path

    def plot_digraph_heatmap(
        self,
        digraph_timing: Dict[str, Dict],
        title: str = "Digraph Timing Heatmap",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> Optional[str]:
        """
        Plot heatmap of digraph (letter pair) timing.

        Args:
            digraph_timing: Dict of digraph -> {mean_ms, std_ms}
            title: Plot title
            save_path: Path to save
            show: Whether to display

        Returns:
            Path to saved image
        """
        if not HAS_MATPLOTLIB or not HAS_NUMPY:
            return None

        letters = 'abcdefghijklmnopqrstuvwxyz'
        n = len(letters)

        # Create timing matrix
        matrix = np.zeros((n, n))
        matrix[:] = np.nan  # Use NaN for missing data

        for digraph, timing in digraph_timing.items():
            parts = digraph.split('_')
            if len(parts) == 2:
                c1, c2 = parts
                if c1 in letters and c2 in letters:
                    i = letters.index(c1)
                    j = letters.index(c2)
                    matrix[i, j] = timing.get('mean_ms', timing.get('mean', 0))

        fig, ax = plt.subplots(figsize=(14, 12))

        # Create heatmap
        im = ax.imshow(matrix, cmap='RdYlGn_r', aspect='equal')

        # Add colorbar
        cbar = fig.colorbar(im, ax=ax, label='Mean IKI (ms)')

        # Add labels
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(list(letters))
        ax.set_yticklabels(list(letters))

        ax.set_xlabel('Second Letter')
        ax.set_ylabel('First Letter')
        ax.set_title(title)

        # Rotate x labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        plt.tight_layout()

        saved_path = save_path or str(self.output_dir / "digraph_heatmap.png")
        plt.savefig(saved_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return saved_path

    def plot_profile_summary(
        self,
        profile: Dict,
        title: str = "Profile Summary",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> Optional[str]:
        """
        Create summary visualization of a profile.

        Args:
            profile: Profile dictionary
            title: Plot title
            save_path: Path to save
            show: Whether to display

        Returns:
            Path to saved image
        """
        if not HAS_MATPLOTLIB:
            return None

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Acceleration profile
        ax1 = axes[0, 0]
        accel = profile.get('mouse', {}).get('acceleration_profile', [])
        if accel:
            x = list(range(len(accel)))
            ax1.fill_between(x, accel, alpha=0.3)
            ax1.plot(x, accel, 'b-', linewidth=2)
            ax1.set_xlabel('Movement Progress (%)')
            ax1.set_ylabel('Normalized Velocity')
            ax1.set_title('Velocity Profile During Movement')
            ax1.set_xticks(x)
            ax1.set_xticklabels([f'{i*10}%' for i in range(len(accel))])
        ax1.grid(True, alpha=0.3)

        # 2. Mouse characteristics
        ax2 = axes[0, 1]
        mouse = profile.get('mouse', {})
        metrics = {
            'Velocity\n(px/s)': mouse.get('velocity', {}).get('mean_pixels_per_sec', 0) / 10,
            'Click\n(ms)': mouse.get('clicks', {}).get('duration_mean_ms', 0),
            'Overshoot\n(%)': mouse.get('trajectory', {}).get('overshoot_rate', 0) * 100,
            'Jitter\n(px)': mouse.get('jitter', {}).get('amplitude_pixels', 0) * 10,
        }

        bars = ax2.bar(metrics.keys(), metrics.values(), color=['blue', 'green', 'orange', 'red'])
        ax2.set_title('Mouse Characteristics (scaled)')
        ax2.set_ylabel('Value')

        # 3. Keyboard characteristics
        ax3 = axes[1, 0]
        keyboard = profile.get('keyboard', {})
        kb_metrics = {
            'WPM': keyboard.get('speed', {}).get('wpm_mean', 0),
            'IKI\n(ms)': keyboard.get('timing', {}).get('inter_key_interval_mean_ms', 0),
            'Hold\n(ms)': keyboard.get('timing', {}).get('hold_duration_mean_ms', 0),
            'Error\n(%)': keyboard.get('errors', {}).get('rate_per_100_keys', 0),
        }

        ax3.bar(kb_metrics.keys(), kb_metrics.values(), color=['purple', 'cyan', 'magenta', 'gray'])
        ax3.set_title('Keyboard Characteristics')
        ax3.set_ylabel('Value')

        # 4. Fitts's Law
        ax4 = axes[1, 1]
        fitts = profile.get('mouse', {}).get('fitts_law', {})
        a = fitts.get('a', 50)
        b = fitts.get('b', 150)
        r2 = fitts.get('r_squared', 0)

        if HAS_NUMPY:
            id_range = np.linspace(0, 5, 100)
            times = a + b * id_range
            ax4.plot(id_range, times, 'b-', linewidth=2)
            ax4.fill_between(id_range, times, alpha=0.3)

        ax4.set_xlabel('Index of Difficulty (bits)')
        ax4.set_ylabel('Movement Time (ms)')
        ax4.set_title(f"Fitts's Law: T = {a:.1f} + {b:.1f}×ID (R²={r2:.3f})")
        ax4.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

        saved_path = save_path or str(self.output_dir / "profile_summary.png")
        plt.savefig(saved_path, dpi=150, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return saved_path

    def visualize_session(
        self,
        session_path: str,
        show: bool = True
    ) -> Dict[str, str]:
        """
        Create all visualizations for a session.

        Args:
            session_path: Path to session directory
            show: Whether to display plots

        Returns:
            Dict of visualization type -> saved path
        """
        session_dir = Path(session_path)
        results = {}

        # Load mouse events
        mouse_file = session_dir / "mouse_events.jsonl"
        if mouse_file.exists():
            mouse_events = []
            with open(mouse_file) as f:
                for line in f:
                    mouse_events.append(json.loads(line))

            if mouse_events:
                path = self.plot_mouse_trajectory(mouse_events, show=show)
                if path:
                    results['trajectory'] = path

                path = self.plot_velocity_profile(mouse_events, show=show)
                if path:
                    results['velocity'] = path

        # Load keyboard events
        keyboard_file = session_dir / "keyboard_events.jsonl"
        if keyboard_file.exists():
            keyboard_events = []
            with open(keyboard_file) as f:
                for line in f:
                    keyboard_events.append(json.loads(line))

            if keyboard_events:
                path = self.plot_typing_rhythm(keyboard_events, show=show)
                if path:
                    results['typing'] = path

        # Load digraph data
        digraph_file = session_dir / "digraph_timing.json"
        if digraph_file.exists():
            with open(digraph_file) as f:
                digraphs = json.load(f)

            if digraphs:
                path = self.plot_digraph_heatmap(digraphs, show=show)
                if path:
                    results['digraphs'] = path

        logger.info(f"Created {len(results)} visualizations for session")

        return results
