from enum import Enum
from typing import Callable
from qtpy import QtCore, QtGui, QtWidgets
import pypho_timeline.EXTERNAL.pyqtgraph as pg
from dataclasses import dataclass

class DragUpdateAction(Enum):
    TRANSLATE = 'translate'
    ALIGN_START = 'align_start'
    ALIGN_FULL = 'align_full'
    

@dataclass
class MouseInteractionCriteria(object):
    """Docstring for MouseInteractionCriteria."""
    drag: Callable
    hover: Callable
    click: Callable
    

class DraggableGraphicsWidgetMixin:
    """ 

    Requires:
        self.custom_mouse_click_criteria_fn
        self.movable
        
    
    from pypho_timeline._embed.DraggableGraphicsWidgetMixin import MouseInteractionCriteria, DraggableGraphicsWidgetMixin, DragUpdateAction
    """
    
    def DraggableGraphicsWidgetMixin_initUI(self):
        pass


    # ==================================================================================================================== #
    # Events                                                                                                               #
    # ==================================================================================================================== #
    
    def mouseDragEvent(self, ev):
        drag_criteria_fn = self.custom_mouse_drag_criteria_fn
        if drag_criteria_fn is None:
            drag_criteria_fn = lambda an_evt: (an_evt.button() == QtCore.Qt.MouseButton.LeftButton) # 
            
        if not self.movable or not drag_criteria_fn(ev):
            return
        ev.accept()
        
        if ev.isStart():
            bdp = ev.buttonDownPos()
            self.cursorOffsets = [l.pos() - bdp for l in self.lines]
            self.startPositions = [l.pos() for l in self.lines]
            self.moving = True
            
        if not self.moving:
            return
            
        self.lines[0].blockSignals(True)  # only want to update once
        for i, l in enumerate(self.lines):
            l.setPos(self.cursorOffsets[i] + ev.pos())
        self.lines[0].blockSignals(False)
        self.prepareGeometryChange()
        
        if ev.isFinish():
            self.moving = False
            self.sigRegionChangeFinished.emit(self)
        else:
            self.sigRegionChanged.emit(self)
            
    def mouseClickEvent(self, ev):
        click_criteria_fn = self.custom_mouse_click_criteria_fn
        if click_criteria_fn is None:
            click_criteria_fn = lambda an_evt: (an_evt.button() == QtCore.Qt.MouseButton.RightButton) # Original/Default Condition
            
        if self.moving and click_criteria_fn(ev):
            ev.accept()
            for i, l in enumerate(self.lines):
                l.setPos(self.startPositions[i])
            self.moving = False
            self.sigRegionChanged.emit(self)
            self.sigRegionChangeFinished.emit(self)

    def hoverEvent(self, ev):
        hover_criteria_fn = self.custom_mouse_hover_criteria_fn
        if hover_criteria_fn is None:
            hover_criteria_fn = lambda an_evt: (an_evt.acceptDrags(QtCore.Qt.MouseButton.LeftButton))
        if self.movable and (not ev.isExit()) and hover_criteria_fn(ev):
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)
            