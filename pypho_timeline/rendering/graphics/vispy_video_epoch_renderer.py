"""VispyVideoEpochRenderer - High-performance GPU-accelerated renderer for video epoch rectangles.

Uses vispy's instanced rendering for efficient real-time updates of video intervals
aligned on a datetime axis.
"""
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from qtpy import QtCore, QtWidgets

try:
    import vispy
    import vispy.scene
    from vispy.scene import visuals
    from vispy.scene.cameras import PanZoomCamera
    from vispy.visuals import Visual
    from vispy import gloo
    from vispy.color import Color
    VISPY_AVAILABLE = True
except ImportError:
    VISPY_AVAILABLE = False
    vispy = None

from pypho_timeline.utils.logging_util import get_rendering_logger
from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_float

logger = get_rendering_logger(__name__)


class InstancedEpochQuadVisual(Visual):
    """Custom vispy Visual using instanced rendering for epoch rectangles.
    
    Renders multiple rectangles efficiently using a single draw call with
    per-instance attributes for position, size, and color.
    """
    
    def __init__(self, max_epochs: int = 10000):
        """Initialize the instanced quad visual.
        
        Args:
            max_epochs: Maximum number of epochs to support (for buffer pre-allocation)
        """
        if not VISPY_AVAILABLE:
            raise ImportError("vispy is required for InstancedEpochQuadVisual. Install with: pip install vispy")
        
        # Vertex shader: transforms unit quad by instance attributes
        vertex_shader = """
        attribute vec2 a_position;        // unit quad vertex [0,0] to [1,1]
        attribute vec2 a_shift;           // per-instance: x_start, y
        attribute vec2 a_size;            // per-instance: width, height
        attribute vec4 a_color;           // per-instance: rgba color
        
        uniform mat4 u_transform;        // world transform
        
        varying vec4 v_color;
        
        void main() {
            // Transform unit quad: shift + size * position
            vec2 pos = a_shift + a_position * a_size;
            gl_Position = u_transform * vec4(pos, 0.0, 1.0);
            v_color = a_color;
        }
        """
        
        # Fragment shader: simple color output
        fragment_shader = """
        varying vec4 v_color;
        void main() {
            gl_FragColor = v_color;
        }
        """
        
        Visual.__init__(self, vertex_shader, fragment_shader)
        
        # Unit quad vertices (two triangles forming a rectangle)
        unit_quad = np.array([
            [0.0, 0.0],  # Triangle 1
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 0.0],  # Triangle 2
            [1.0, 1.0],
            [0.0, 1.0]
        ], dtype=np.float32)
        
        # Create vertex buffer for unit quad
        self.vbo = gloo.VertexBuffer(unit_quad)
        self.shared_program.vert['a_position'] = self.vbo
        self._draw_mode = 'triangles'
        
        # Pre-allocate buffers for instances
        self.max_epochs = max_epochs
        self.shifts = gloo.VertexBuffer(np.zeros((max_epochs, 2), dtype=np.float32), divisor=1)
        self.sizes = gloo.VertexBuffer(np.zeros((max_epochs, 2), dtype=np.float32), divisor=1)
        self.colors = gloo.VertexBuffer(np.zeros((max_epochs, 4), dtype=np.float32), divisor=1)
        
        # Set instance attributes
        self.shared_program.vert['a_shift'] = self.shifts
        self.shared_program.vert['a_size'] = self.sizes
        self.shared_program.vert['a_color'] = self.colors
        
        self.instance_count = 0  # Number of active epochs
        
        # Set GL state for 2D rendering
        self.set_gl_state('translucent', blend=True, depth_test=False)
    
    def set_epochs(self, epochs_data: List[Dict[str, Any]], reference_datetime: Optional[datetime] = None):
        """Update epoch rectangles from data.
        
        Args:
            epochs_data: List of dicts with keys: 't_start', 't_duration', 'series_vertical_offset',
                        'series_height', 'pen', 'brush' (or 'color')
            reference_datetime: Optional reference datetime for time conversion
        """
        n = len(epochs_data)
        if n > self.max_epochs:
            logger.warning(f"InstancedEpochQuadVisual: {n} epochs exceeds max_epochs={self.max_epochs}, truncating")
            epochs_data = epochs_data[:self.max_epochs]
            n = self.max_epochs
        
        # Pre-allocate arrays
        shifts = np.zeros((self.max_epochs, 2), dtype=np.float32)
        sizes = np.zeros((self.max_epochs, 2), dtype=np.float32)
        colors = np.zeros((self.max_epochs, 4), dtype=np.float32)
        
        # Convert datetime to float if needed
        def time_to_float(t_val):
            """Convert time value to float."""
            if isinstance(t_val, datetime):
                if reference_datetime is None:
                    return t_val.timestamp()
                else:
                    return datetime_to_float(t_val, reference_datetime)
            return float(t_val)
        
        # Extract color from pen/brush
        def extract_color(pen_or_brush):
            """Extract RGBA color from pen or brush object."""
            if hasattr(pen_or_brush, 'color'):
                c = pen_or_brush.color()
                if hasattr(c, 'getRgbF'):
                    r, g, b, a = c.getRgbF()
                    return np.array([r, g, b, a], dtype=np.float32)
                elif hasattr(c, 'getRgb'):
                    r, g, b = c.getRgb()
                    return np.array([r/255.0, g/255.0, b/255.0, 1.0], dtype=np.float32)
            # Fallback: default blue color
            return np.array([0.4, 0.6, 0.8, 0.588], dtype=np.float32)
        
        # Process each epoch
        for i, epoch in enumerate(epochs_data):
            t_start = time_to_float(epoch.get('t_start', 0.0))
            t_duration = float(epoch.get('t_duration', 1.0))
            t_end = t_start + t_duration
            
            y_offset = float(epoch.get('series_vertical_offset', 0.0))
            y_height = float(epoch.get('series_height', 1.0))
            
            # Extract color from brush (preferred) or pen
            brush = epoch.get('brush', None)
            pen = epoch.get('pen', None)
            if brush is not None:
                color = extract_color(brush)
            elif pen is not None:
                color = extract_color(pen)
            else:
                # Default blue color matching VideoTrackDatasource
                color = np.array([0.4, 0.6, 0.8, 0.588], dtype=np.float32)
            
            # Set instance attributes
            shifts[i, 0] = t_start
            shifts[i, 1] = y_offset
            sizes[i, 0] = t_duration  # width
            sizes[i, 1] = y_height    # height
            colors[i] = color
        
        # Upload to GPU buffers
        self.shifts.set_data(shifts)
        self.sizes.set_data(sizes)
        self.colors.set_data(colors)
        
        self.instance_count = n
    
    def _prepare_transforms(self, view):
        """Called by SceneCanvas to set transform uniform."""
        self.shared_program.vert['u_transform'] = view.get_transform()
    
    def draw(self, transforms):
        """Draw the instanced rectangles."""
        if self.instance_count == 0:
            return
        
        self._program = self.shared_program
        self._program.vert['a_position'] = self.vbo
        self._program.draw('triangles', vertices=self.vbo, instances=self.instance_count)


class VispyVideoEpochRenderer(QtCore.QObject):
    """High-performance vispy-based renderer for video epoch rectangles.
    
    Manages a vispy SceneCanvas with instanced rendering for efficient
    real-time updates of video intervals aligned on a datetime axis.
    """
    
    def __init__(self, parent_widget: Optional[QtWidgets.QWidget] = None, reference_datetime: Optional[datetime] = None, max_epochs: int = 10000):
        """Initialize the vispy renderer.
        
        Args:
            parent_widget: Optional Qt widget to embed the canvas in
            reference_datetime: Reference datetime for time axis alignment
            max_epochs: Maximum number of epochs to support
        """
        if not VISPY_AVAILABLE:
            raise ImportError("vispy is required for VispyVideoEpochRenderer. Install with: pip install vispy")
        
        super().__init__(parent_widget)
        
        self.reference_datetime = reference_datetime
        self.max_epochs = max_epochs
        
        # Create vispy SceneCanvas
        # Note: parent_widget may be None initially, canvas can be embedded later
        self.canvas = vispy.scene.SceneCanvas(keys='interactive', show=False, parent=parent_widget)
        if hasattr(self.canvas, '_send_hover_events'):
            self.canvas._send_hover_events = True  # Enable hover events
        
        # Create viewbox for the scene
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = PanZoomCamera(aspect=1.0)
        
        # Create instanced visual for epochs
        self.epoch_visual = InstancedEpochQuadVisual(max_epochs=max_epochs)
        self.view.add(self.epoch_visual)
        
        # Add axis at bottom with datetime formatting
        self.axis = visuals.Axis(orientation='bottom', parent=self.view.scene)
        self.axis.transform = self.view.scene.transform
        # Store axis formatter function
        self._axis_formatter = None
        if reference_datetime is not None:
            self._setup_datetime_axis()
        
        # Store current data
        self.current_epochs_data: List[Dict[str, Any]] = []
        self.viewport_start: Optional[float] = None
        self.viewport_end: Optional[float] = None
        
        # Performance optimization: rate limiting for updates
        self._update_timer = QtCore.QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._deferred_update)
        self._pending_update = False
        self._pending_epochs_df: Optional[pd.DataFrame] = None
        self._update_rate_limit_ms = 16  # ~60fps max update rate
        
        logger.info(f"VispyVideoEpochRenderer initialized with max_epochs={max_epochs}")
    
    def _setup_datetime_axis(self):
        """Setup datetime axis formatting."""
        if self.reference_datetime is None:
            return
        
        # Custom tick formatter for datetime
        def format_tick(value, scale, spacing):
            """Format tick value as datetime string."""
            try:
                # Convert float to datetime
                dt = float_to_datetime(float(value), self.reference_datetime)
                # Format as readable date/time
                return dt.strftime('%m/%d %H:%M:%S')
            except Exception:
                return f"{value:.1f}"
        
        # Note: vispy's Axis doesn't have a direct tick formatter API like pyqtgraph
        # We'll handle formatting in update methods if needed
        self._axis_formatter = format_tick
    
    def update_epochs(self, epochs_df: pd.DataFrame, viewport_start: Optional[float] = None, viewport_end: Optional[float] = None):
        """Update the rendered epochs from a DataFrame.
        
        Args:
            epochs_df: DataFrame with columns ['t_start', 't_duration', 'series_vertical_offset',
                       'series_height', 'pen', 'brush']
            viewport_start: Optional viewport start time for culling
            viewport_end: Optional viewport end time for culling
        """
        # Rate limiting: defer update if timer is active
        if self._update_timer.isActive():
            self._pending_update = True
            self._pending_epochs_df = epochs_df.copy()
            self._pending_viewport_start = viewport_start
            self._pending_viewport_end = viewport_end
            return
        
        # Perform immediate update
        self._do_update_epochs(epochs_df, viewport_start, viewport_end)
        
        # Start rate limit timer
        self._update_timer.start(self._update_rate_limit_ms)
    
    def _deferred_update(self):
        """Handle deferred update after rate limit timer expires."""
        if self._pending_update and self._pending_epochs_df is not None:
            self._do_update_epochs(
                self._pending_epochs_df,
                getattr(self, '_pending_viewport_start', None),
                getattr(self, '_pending_viewport_end', None)
            )
            self._pending_update = False
            self._pending_epochs_df = None
    
    def _do_update_epochs(self, epochs_df: pd.DataFrame, viewport_start: Optional[float] = None, viewport_end: Optional[float] = None):
        """Internal method to perform the actual update."""
        if epochs_df.empty:
            self.epoch_visual.set_epochs([], self.reference_datetime)
            self.current_epochs_data = []
            self.canvas.update()
            return
        
        # Apply viewport culling if provided
        if viewport_start is not None and viewport_end is not None:
            self.viewport_start = viewport_start
            self.viewport_end = viewport_end
            # Filter epochs overlapping viewport
            mask = (epochs_df['t_start'] + epochs_df['t_duration'] >= viewport_start) & \
                   (epochs_df['t_start'] <= viewport_end)
            epochs_df = epochs_df[mask].copy()
        
        # Convert DataFrame to list of dicts
        epochs_data = []
        for idx, row in epochs_df.iterrows():
            epochs_data.append({
                't_start': row.get('t_start', 0.0),
                't_duration': row.get('t_duration', 1.0),
                'series_vertical_offset': row.get('series_vertical_offset', 0.0),
                'series_height': row.get('series_height', 1.0),
                'pen': row.get('pen', None),
                'brush': row.get('brush', None),
            })
        
        # Update visual (buffer reuse is handled internally)
        self.epoch_visual.set_epochs(epochs_data, self.reference_datetime)
        self.current_epochs_data = epochs_data
        
        # Update camera range if needed
        if len(epochs_df) > 0:
            t_start = epochs_df['t_start'].min()
            t_end = (epochs_df['t_start'] + epochs_df['t_duration']).max()
            y_min = epochs_df['series_vertical_offset'].min()
            y_max = (epochs_df['series_vertical_offset'] + epochs_df['series_height']).max()
            
            # Set camera range (with padding)
            padding_x = (t_end - t_start) * 0.1 if t_end > t_start else 1.0
            padding_y = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            self.view.camera.set_range(
                x=(t_start - padding_x, t_end + padding_x),
                y=(y_min - padding_y, y_max + padding_y)
            )
        
        # Trigger redraw
        self.canvas.update()
    
    def set_viewport(self, viewport_start: float, viewport_end: float):
        """Update the viewport and re-render visible epochs.
        
        Args:
            viewport_start: Start time of viewport
            viewport_end: End time of viewport
        """
        self.viewport_start = viewport_start
        self.viewport_end = viewport_end
        
        # Update camera range
        y_range = self.view.camera.rect[2:4] if hasattr(self.view.camera, 'rect') else (0, 1)
        self.view.camera.set_range(x=(viewport_start, viewport_end), y=y_range)
        
        # Re-render with culling
        if self.current_epochs_data:
            # Rebuild from current data with new viewport
            epochs_df = pd.DataFrame(self.current_epochs_data)
            self.update_epochs(epochs_df, viewport_start, viewport_end)
        else:
            self.canvas.update()
    
    def get_canvas_widget(self) -> QtWidgets.QWidget:
        """Get the Qt widget for the vispy canvas.
        
        Returns:
            Qt widget that can be embedded in layouts
        """
        return self.canvas.native
    
    def remove(self):
        """Clean up the renderer."""
        # Stop update timer
        if hasattr(self, '_update_timer') and self._update_timer is not None:
            self._update_timer.stop()
        if hasattr(self, 'canvas') and self.canvas is not None:
            self.canvas.close()
        self.current_epochs_data = []


__all__ = ['VispyVideoEpochRenderer', 'InstancedEpochQuadVisual', 'VISPY_AVAILABLE']
