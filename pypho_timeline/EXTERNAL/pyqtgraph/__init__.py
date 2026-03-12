"""
PyQtGraph - Scientific Graphics and GUI Library for Python
www.pyqtgraph.org
"""

__version__ = '0.12.4.dev1'

### import all the goodies and add some helper functions for easy CLI use

import os
import sys

import numpy  # # pyqtgraph requires numpy

# ## 'Qt' is a local module; it is intended mainly to cover up the differences
# ## between PyQt and PySide.
from .colors import palette
from .Qt import QtCore, QtGui, QtWidgets
from .Qt import exec_ as exec
from .Qt import mkQApp

## Import almost everything to make it available from a single namespace
## don't import the more complex systems--canvas, parametertree, flowchart, dockarea
## these must be imported separately.
#from . import frozenSupport
#def importModules(path, globals, locals, excludes=()):
    #"""Import all modules residing within *path*, return a dict of name: module pairs.
    
    #Note that *path* MUST be relative to the module doing the import.    
    #"""
    #d = os.path.join(os.path.split(globals['__file__'])[0], path)
    #files = set()
    #for f in frozenSupport.listdir(d):
        #if frozenSupport.isdir(os.path.join(d, f)) and f not in ['__pycache__', 'tests']:
            #files.add(f)
        #elif f[-3:] == '.py' and f != '__init__.py':
            #files.add(f[:-3])
        #elif f[-4:] == '.pyc' and f != '__init__.pyc':
            #files.add(f[:-4])
        
    #mods = {}
    #path = path.replace(os.sep, '.')
    #for modName in files:
        #if modName in excludes:
            #continue
        #try:
            #if len(path) > 0:
                #modName = path + '.' + modName
            #print( "from .%s import * " % modName)
            #mod = __import__(modName, globals, locals, ['*'], 1)
            #mods[modName] = mod
        #except:
            #import traceback
            #traceback.print_stack()
            #sys.excepthook(*sys.exc_info())
            #print("[Error importing module: %s]" % modName)
            
    #return mods

#def importAll(path, globals, locals, excludes=()):
    #"""Given a list of modules, import all names from each module into the global namespace."""
    #mods = importModules(path, globals, locals, excludes)
    #for mod in mods.values():
        #if hasattr(mod, '__all__'):
            #names = mod.__all__
        #else:
            #names = [n for n in dir(mod) if n[0] != '_']
        #for k in names:
            #if hasattr(mod, k):
                #globals[k] = getattr(mod, k)

# Dynamic imports are disabled. This causes too many problems.
#importAll('graphicsItems', globals(), locals())
#importAll('widgets', globals(), locals(),
          #excludes=['MatplotlibWidget', 'RawImageWidget', 'RemoteGraphicsView'])

# ## Attempts to work around exit crashes:
# import atexit

# from .colormap import *
# from .functions import *
# from .graphicsItems.ArrowItem import *
# from .graphicsItems.AxisItem import *
# from .graphicsItems.BarGraphItem import *
# from .graphicsItems.ButtonItem import *
# from .graphicsItems.ColorBarItem import *
# from .graphicsItems.CurvePoint import *
# from .graphicsItems.DateAxisItem import *
# from .graphicsItems.ErrorBarItem import *
# from .graphicsItems.FillBetweenItem import *
# from .graphicsItems.GradientEditorItem import *
# from .graphicsItems.GradientLegend import *
# from .graphicsItems.GraphicsItem import *
# from .graphicsItems.GraphicsLayout import *
# from .graphicsItems.GraphicsObject import *
# from .graphicsItems.GraphicsWidget import *
# from .graphicsItems.GraphicsWidgetAnchor import *
# from .graphicsItems.GraphItem import *
# from .graphicsItems.GridItem import *
# from .graphicsItems.HistogramLUTItem import *
# from .graphicsItems.ImageItem import *
# from .graphicsItems.InfiniteLine import *
# from .graphicsItems.IsocurveItem import *
# from .graphicsItems.ItemGroup import *
# from .graphicsItems.LabelItem import *
# from .graphicsItems.LegendItem import *
# from .graphicsItems.LinearRegionItem import *
# from .graphicsItems.MultiPlotItem import *
# from .graphicsItems.PColorMeshItem import *
# from .graphicsItems.PlotCurveItem import *
# from .graphicsItems.PlotDataItem import *
# from .graphicsItems.PlotItem import *
# from .graphicsItems.ROI import *
# from .graphicsItems.ScaleBar import *
# from .graphicsItems.ScatterPlotItem import *
# from .graphicsItems.TargetItem import *
# from .graphicsItems.TextItem import *
# from .graphicsItems.UIGraphicsItem import *
# from .graphicsItems.ViewBox import *
# from .graphicsItems.VTickGroup import *

# # indirect imports used within library
# from .GraphicsScene import GraphicsScene
# from .graphicsWindows import *
# from .imageview import *

# # indirect imports known to be used outside of the library
# from .metaarray import MetaArray
# from .ordereddict import OrderedDict
# from .Point import Point
# from .ptime import time
# from .Qt import isQObjectAlive
# from .SignalProxy import *
# from .SRTTransform import SRTTransform
# from .SRTTransform3D import SRTTransform3D
# from .ThreadsafeTimer import *
# from .Transform3D import Transform3D
# from .util.cupy_helper import getCupy
# from .Vector import Vector
# from .WidgetGroup import *
# from .widgets.BusyCursor import *
# from .widgets.CheckTable import *
# from .widgets.ColorButton import *
# from .widgets.ColorMapWidget import *
# from .widgets.ComboBox import *
# from .widgets.DataFilterWidget import *
# from .widgets.DataTreeWidget import *
# from .widgets.DiffTreeWidget import *
# from .widgets.FeedbackButton import *
# from .widgets.FileDialog import *
# from .widgets.GradientWidget import *
# from .widgets.GraphicsLayoutWidget import *
# from .widgets.GraphicsView import *
# from .widgets.GroupBox import GroupBox
# from .widgets.HistogramLUTWidget import *
# from .widgets.JoystickButton import *
# from .widgets.LayoutWidget import *
# from .widgets.MultiPlotWidget import *
# from .widgets.PathButton import *
# from .widgets.PlotWidget import *
# from .widgets.ProgressDialog import *
# from .widgets.RemoteGraphicsView import RemoteGraphicsView
# from .widgets.ScatterPlotWidget import *
# from .widgets.SpinBox import *
# from .widgets.TableWidget import *
# from .widgets.TreeWidget import *
# from .widgets.ValueLabel import *
from .widgets.VerticalLabel import *

