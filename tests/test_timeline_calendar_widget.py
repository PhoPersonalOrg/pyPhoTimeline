
import sys
from datetime import datetime, timedelta, timezone
from qtpy import QtWidgets, QtCore
import pyqtgraph as pg
from pypho_timeline.widgets.timeline_calendar_widget import TimelineCalendarWidget

def test_calendar_widget():
    app = QtWidgets.QApplication(sys.argv)
    
    # Create window
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("TimelineCalendarWidget Test")
    win.resize(800, 200)
    
    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central_widget)
    win.setCentralWidget(central_widget)
    
    # Create calendar
    calendar = TimelineCalendarWidget()
    layout.addWidget(calendar)
    
    # Set range: 7 days ago to today
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=7)
    
    calendar.set_total_range(start_dt, end_dt)
    
    # Set active window: 1 hour in the middle
    window_start = start_dt + timedelta(days=3)
    window_end = window_start + timedelta(hours=2)
    calendar.set_active_window(window_start, window_end)
    
    # Connect signal
    def on_window_changed(start, end):
        dt_start = datetime.fromtimestamp(start, tz=timezone.utc)
        dt_end = datetime.fromtimestamp(end, tz=timezone.utc)
        print(f"Window changed: {dt_start} to {dt_end}")
        
    calendar.sigWindowChanged.connect(on_window_changed)
    
    # Add a label to show values
    label = QtWidgets.QLabel("Drag the blue region or click anywhere to jump.")
    layout.addWidget(label)
    
    win.show()
    
    # For testing in non-interactive environment, we can just run for a few seconds if possible
    # but here we just exit if it's a script.
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        QtCore.QTimer.singleShot(1000, app.quit)
        
    sys.exit(app.exec_())

if __name__ == "__main__":
    test_calendar_widget()
