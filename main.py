"""
Main script for Dual Radar with TI Industrial Visualizer
Connects thesis fusion code to Industrial Visualizer GUI
"""

import sys
import os
from multiprocessing import Process, Manager
from time import sleep

# Your thesis code
from library.radar_reader_dual_1010 import RadarReader
from library.sync_monitor import SyncMonitor

# Adapter for Industrial Visualizer
from industrial_visualizer_adapter import IndustrialVisualizerAdapter
from gui_core_modified import launch_industrial_visualizer_gui

# Configuration
from cfg.config_demo_dual_radar import *

# Logging
import logging
logging.basicConfig(
    format='%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)


def radar_proc_method(_run_flag, _radar_rd_queue, _shared_param_dict, **_kwargs_CFG):
    """Radar process: Parse TLV 1010 → Transform → Queue"""
    radar = RadarReader(
        run_flag=_run_flag,
        radar_rd_queue=_radar_rd_queue,
        shared_param_dict=_shared_param_dict,
        **_kwargs_CFG
    )
    radar.run()


def monitor_proc_method(_run_flag, _radar_rd_queue_list, _shared_param_dict, **_kwargs_CFG):
    """Sync monitor: Keep queues aligned"""
    sync = SyncMonitor(
        run_flag=_run_flag,
        radar_rd_queue_list=_radar_rd_queue_list,
        shared_param_dict=_shared_param_dict,
        **_kwargs_CFG
    )
    sync.run()


if __name__ == '__main__':
    print("="*70)
    print("DUAL RADAR WITH TI INDUSTRIAL VISUALIZER")
    print(f"Radars: {len(RADAR_CFG_LIST)}")
    print("="*70)
    
    # Set Qt attributes BEFORE any QApplication import
    import os
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    
    # Generate shared variables
    run_flag = Manager().Value('b', True)
    shared_param_dict = {
        'proc_status_dict': Manager().dict()
    }
    
    # Generate queues and radar processes
    radar_rd_queue_list = []
    proc_list = []
    
    print("\nInitializing radars...")
    for i, RADAR_CFG in enumerate(RADAR_CFG_LIST):
        print(f"  [{i+1}] {RADAR_CFG['name']}: "
              f"CFG={RADAR_CFG['cfg_port_name']}, "
              f"DATA={RADAR_CFG['data_port_name']}")
        
        # Create queue
        radar_rd_queue = Manager().Queue()
        radar_rd_queue_list.append(radar_rd_queue)
        
        # Create config
        kwargs_CFG = {
            'RADAR_CFG': RADAR_CFG,
            'FRAME_EARLY_PROCESSOR_CFG': FRAME_EARLY_PROCESSOR_CFG
        }
        
        # Create process
        radar_proc = Process(
            target=radar_proc_method,
            args=(run_flag, radar_rd_queue, shared_param_dict),
            kwargs=kwargs_CFG,
            name=RADAR_CFG['name']
        )
        proc_list.append(radar_proc)
    
    # Configuration for adapter
    kwargs_CFG = {
        'VISUALIZER_CFG': VISUALIZER_CFG,
        'RADAR_CFG_LIST': RADAR_CFG_LIST,
        'SYNC_MONITOR_CFG': SYNC_MONITOR_CFG,
        'TRACK_FUSION_CFG': TRACK_FUSION_CFG
    }
    
    # Create sync monitor process
    # print("Initializing sync monitor...")
    # monitor_proc = Process(
    #     target=monitor_proc_method,
    #     args=(run_flag, radar_rd_queue_list, shared_param_dict),
    #     kwargs=kwargs_CFG,
    #     name='Module_SCM'
    # )
    # proc_list.append(monitor_proc)
    
    # Create adapter (runs in main thread with GUI)
    print("Initializing Industrial Visualizer adapter...")
    adapter = IndustrialVisualizerAdapter(
        run_flag=run_flag,
        radar_rd_queue_list=radar_rd_queue_list,
        shared_param_dict=shared_param_dict,
        **kwargs_CFG
    )
    
    # Initialize process status
    for proc in proc_list:
        shared_param_dict['proc_status_dict'][proc.name] = False
    
    # Start all background processes
    print("\n" + "="*70)
    print("STARTING PROCESSES...")
    print("="*70)
    for proc in proc_list:
        print(f"Starting {proc.name}...")
        proc.start()
        sleep(0.5)
    
    # Launch Industrial Visualizer GUI in main thread
    print("\n" + "="*70)
    print("LAUNCHING INDUSTRIAL VISUALIZER GUI...")
    print("="*70)
    
    try:
        # Import Qt components (after setting environment)
        from PySide2.QtWidgets import QApplication
        from PySide2.QtCore import Qt
        
        # Setup Qt Application
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Launch GUI with adapter
        main_window = launch_industrial_visualizer_gui(adapter)
        
        # Start adapter in background (non-blocking)
        from threading import Thread
        adapter_thread = Thread(target=adapter.run, daemon=True)
        adapter_thread.start()
        
        print("\n" + "="*70)
        print("SYSTEM RUNNING")
        print("="*70)
        print("Industrial Visualizer GUI is now open")
        print("Click 'Start Visualization' to begin\n")
        
        # Run Qt event loop (blocks here)
        sys.exit(app.exec_())
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\n" + "="*70)
        print("STOPPING SYSTEM...")
        print("="*70)
        run_flag.value = False
        
        sleep(2)
        
        # Terminate processes
        for proc in proc_list:
            if proc.is_alive():
                print(f"Terminating {proc.name}...")
                proc.terminate()
                proc.join(timeout=1)
        
        print("\n" + "="*70)
        print("SYSTEM STOPPED")
        print("="*70)