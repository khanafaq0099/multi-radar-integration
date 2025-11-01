"""
Modified gui_core.py to work with thesis fusion adapter
Replaces UART reading with adapter input
"""

# Standard imports (same as original)
import json
import time
from serial.tools import list_ports
import os
import sys
from contextlib import suppress

# PyQt Imports (same as original)
from PySide2 import QtGui
from PySide2.QtCore import QTimer, Qt
from PySide2.QtWidgets import (
    QAction, QTabWidget, QGridLayout, QMenu, QGroupBox, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QMainWindow, QWidget,
    QShortcut, QSlider, QCheckBox, QMessageBox
)

# Local Imports
from cached_data import CachedDataType
from demo_defines import *

# MODIFIED: Import mock parser instead of real UART parser
from industrial_visualizer_adapter import MockUARTParser

# Import only PeopleTracking demo (for 3D People Tracking)
from people_tracking import PeopleTracking

# Logger
import logging
log = logging.getLogger(__name__)


class Window(QMainWindow):
    """
    Modified Window class - simplified for thesis adapter
    """
    
    def __init__(self, parent=None, size=[], title="Dual Radar Industrial Visualizer", adapter=None):
        super(Window, self).__init__(parent)
        
        # Store adapter reference
        self.adapter = adapter
        
        # Create core with adapter
        self.core = Core(adapter=adapter)
        self.setWindowIcon(QtGui.QIcon("./images/logo.png"))
        
        self.shortcut = QShortcut(QtGui.QKeySequence("Ctrl+W"), self)
        self.shortcut.activated.connect(self.close)
        
        # Set the layout
        self.demoTabs = QTabWidget()
        self.gridLayout = QGridLayout()
        
        # Simplified UI (no COM port selection needed)
        self.initSimplifiedUI()
        
        self.gridLayout.addWidget(self.controlBox, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.demoTabs, 0, 1, 8, 1)
        
        self.gridLayout.setColumnStretch(0, 1)
        self.gridLayout.setColumnStretch(1, 5)
        
        self.central = QWidget()
        self.central.setLayout(self.gridLayout)
        
        self.setWindowTitle(title)
        self.setCentralWidget(self.central)
        self.showMaximized()
        
        # Auto-initialize 3D People Tracking demo
        self.core.initializePeopleTrackingDemo(self.gridLayout, self.demoTabs)
    
    def initSimplifiedUI(self):
        """Simplified UI without COM port selection"""
        self.controlBox = QGroupBox("Control")
        self.controlLayout = QGridLayout()
        
        # Status label
        self.statusLabel = QLabel("Status: Ready")
        self.statusLabel.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        # Start/Stop button
        self.startButton = QPushButton("Start Visualization")
        self.startButton.clicked.connect(self.onStartStop)
        self.startButton.setStyleSheet("background-color: green; font-weight: bold;")
        
        # Info labels
        self.frameCountLabel = QLabel("Frames: 0")
        self.trackCountLabel = QLabel("Tracks: 0")
        
        # Layout
        self.controlLayout.addWidget(self.statusLabel, 0, 0, 1, 2)
        self.controlLayout.addWidget(self.startButton, 1, 0, 1, 2)
        self.controlLayout.addWidget(self.frameCountLabel, 2, 0)
        self.controlLayout.addWidget(self.trackCountLabel, 2, 1)
        
        self.controlBox.setLayout(self.controlLayout)
    
    def onStartStop(self):
        """Start/stop visualization"""
        if self.core.isRunning:
            self.core.stop()
            self.startButton.setText("Start Visualization")
            self.startButton.setStyleSheet("background-color: green; font-weight: bold;")
            self.statusLabel.setText("Status: Stopped")
        else:
            self.core.start()
            self.startButton.setText("Stop Visualization")
            self.startButton.setStyleSheet("background-color: red; font-weight: bold;")
            self.statusLabel.setText("Status: Running")
    
    def updateStats(self, frame_count, track_count):
        """Update statistics display"""
        self.frameCountLabel.setText(f"Frames: {frame_count}")
        self.trackCountLabel.setText(f"Tracks: {track_count}")


class Core:
    """
    Modified Core class - works with adapter instead of UART
    """
    
    def __init__(self, adapter=None):
        self.adapter = adapter
        self.demo = DEMO_3D_PEOPLE_TRACKING
        self.device = "xWR6843"
        self.frameTime = 50  # 20 FPS
        
        # Create mock parser
        self.parser = MockUARTParser(adapter)
        
        # Create People Tracking demo
        self.peopleTrackingDemo = PeopleTracking()
        
        # Timer for updating GUI
        self.updateTimer = QTimer()
        self.updateTimer.setSingleShot(False)
        self.updateTimer.timeout.connect(self.updateGUI)
        
        self.isRunning = False
        
        log.info('Core initialized with adapter')
    
    def initializePeopleTrackingDemo(self, gridLayout, demoTabs):
        """Initialize 3D People Tracking demo"""
        try:
            # Setup GUI for People Tracking
            self.peopleTrackingDemo.setupGUI(gridLayout, demoTabs, self.device)
            log.info('People Tracking demo initialized')
        except Exception as e:
            log.error(f'Error initializing demo: {e}')
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start visualization"""
        if self.adapter:
            # Register update callback
            self.adapter.set_update_callback(self.on_data_update)
            log.info('Adapter callback registered')
        
        # Start update timer
        self.updateTimer.start(int(self.frameTime))
        self.isRunning = True
        log.info('Visualization started')
    
    def stop(self):
        """Stop visualization"""
        self.updateTimer.stop()
        self.isRunning = False
        log.info('Visualization stopped')
    
    def on_data_update(self, output_dict):
        """
        Callback when adapter has new data
        
        Args:
            output_dict: Parsed data in Industrial Viz format
        """
        # Update mock parser's output
        self.parser.update_output(output_dict)
    
    def updateGUI(self):
        """Update GUI with latest data"""
        try:
            # Get latest data from mock parser
            output_dict = self.parser.readAndParseUartDoubleCOMPort()
            
            # Update People Tracking demo
            if output_dict and output_dict.get('numDetectedTracks', 0) > 0:
                self.peopleTrackingDemo.updateGraph(output_dict)
        
        except Exception as e:
            log.error(f'Error updating GUI: {e}')


# Standalone function to launch Industrial Visualizer with adapter
def launch_industrial_visualizer_gui(adapter):
    """
    Launch Industrial Visualizer GUI with adapter
    
    Args:
        adapter: IndustrialVisualizerAdapter instance
    
    Returns:
        Window instance
    """
    from PySide2.QtWidgets import QApplication
    from PySide2.QtCore import Qt
    import sys
    
    # Check if QApplication already exists
    app = QApplication.instance()
    if app is None:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        app = QApplication(sys.argv)
    
    # Get screen size
    screen = app.primaryScreen()
    size = screen.size()
    
    # Create main window
    main = Window(size=size, title="Dual Radar Industrial Visualizer", adapter=adapter)
    main.show()
    
    log.info('Industrial Visualizer GUI launched')
    
    return main