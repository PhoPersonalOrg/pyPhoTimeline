# MainTimelineWindow.py
# Generated from c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.ui automatically by PhoPyQtClassGenerator VSCode Extension
import sys
import os

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QMessageBox, QToolTip, QStackedWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFormLayout, QLabel, QFrame, QPushButton, QTableWidget, QTableWidgetItem, QMainWindow
from PyQt5.QtWidgets import QApplication, QFileSystemModel, QTreeView, QWidget, QHeaderView
from PyQt5.QtGui import QPainter, QBrush, QPen, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, QPoint, QRect, QObject, QEvent, pyqtSignal, pyqtSlot, QSize, QDir

## IMPORTS:
from pypho_timeline.widgets.log_widget import LogWidget, QtLogHandler
from pypho_timeline.utils.logging_util import get_rendering_logger

## Define the .ui file path
path = os.path.dirname(os.path.abspath(__file__))
uiFile = os.path.join(path, 'MainTimelineWindow.ui')

class MainTimelineWindow(QMainWindow):
    def __init__(self, parent=None, show_immediately: bool = True):
        super().__init__(parent=parent) # Call the inherited classes __init__ method
        self.ui = uic.loadUi(uiFile, self) # Load the .ui file
        self.initUI()
        if show_immediately:
            self.show() # Show the GUI

    def initUI(self):
        self.statusBar().hide()
        content_layout = QVBoxLayout(self.contentWidget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.contentWidget.setLayout(content_layout)
        self._log_widget = LogWidget(parent=self.logPanel)
        self.logPanel.layout().addWidget(self._log_widget)
        self.logPanel.setVisible(False)
        self.logToggleButton.setChecked(False)
        self.logToggleButton.setText("Show Log")
        self.logToggleButton.toggled.connect(self._on_log_toggle)
        _log_handler = QtLogHandler(parent=self)
        _log_handler.log_record_received.connect(self._log_widget.append_log)
        get_rendering_logger(__name__).addHandler(_log_handler)
        self._qt_log_handler = _log_handler


    def _on_log_toggle(self, checked: bool):
        self.logPanel.setVisible(checked)
        self.logToggleButton.setText("Hide Log" if checked else "Show Log")


    @property
    def timeline_widget(self):
        layout = self.contentWidget.layout()
        if layout is not None and layout.count() > 0:
            item = layout.itemAt(0)
            if item is not None and item.widget() is not None:
                return item.widget()
        return None


## Start Qt event loop
if __name__ == '__main__':
    app = QApplication([])
    widget = MainTimelineWindow()
    widget.show()
    sys.exit(app.exec_())
