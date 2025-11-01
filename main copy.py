# """
# Main script for Dual Radar with TI Industrial Visualizer
# Connects thesis fusion code to Industrial Visualizer GUI
# """

# import sys
# from multiprocessing import Process, Manager
# from time import sleep

# # PySide2 for GUI
# from PySide2.QtWidgets import QApplication
# from PySide2.QtCore import Qt

# # Your thesis code
# from library.radar_reader_dual_1010 import RadarReader
# from library.sync_monitor import SyncMonitor

# # Adapter for Industrial Visualizer
# from industrial_visualizer_adapter import IndustrialVisualizerAdapter
# from gui_core_modified import launch_industrial_visualizer_gui

# # Configuration
# from cfg.config_demo_dual_radar import *

# # Logging
# import logging
# logging.basicConfig(
#     format='%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
#     level=logging.INFO
# )
# log = logging.getLogger(__name__)


# def radar_proc_method(_run_flag, _radar_rd_queue, _shared_param_dict, **_kwargs_CFG):
#     """Process for each radar - reads and parses TLV 1010 data"""
#     radar = RadarReader(
#         run_flag=_run_flag,
#         radar_rd_queue=_radar_rd_queue,
#         shared_param_dict=_shared_param_dict,
#         **_kwargs_CFG
#     )
#     radar.run()


# # def vis_proc_method(_run_flag, _radar_rd_queue_list, _shared_param_dict, **_kwargs_CFG):
# #     """Visualization process - fuses tracks and outputs to Industrial Visualizer"""
# #     vis = Visualizer(
# #         run_flag=_run_flag,
# #         radar_rd_queue_list=_radar_rd_queue_list,
# #         shared_param_dict=_shared_param_dict,
# #         **_kwargs_CFG
# #     )
# #     vis.run()


# def monitor_proc_method(_run_flag, _radar_rd_queue_list, _shared_param_dict, **_kwargs_CFG):
#     """Monitor process - syncs queues between radars"""
#     sync = SyncMonitor(
#         run_flag=_run_flag,
#         radar_rd_queue_list=_radar_rd_queue_list,
#         shared_param_dict=_shared_param_dict,
#         **_kwargs_CFG
#     )
#     sync.run()


# if __name__ == '__main__':
#     print("="*70)
#     print("DUAL IWR6843AOP 3D PEOPLE TRACKING SYSTEM")
#     print(f"Experiment: {EXPERIMENT_NAME}")
#     print(f"Radars: {len(RADAR_CFG_LIST)}")
#     print("="*70)
    
#     # Generate shared variables between processes
#     run_flag = Manager().Value('b', True)
    
#     # Shared parameter dictionary
#     shared_param_dict = {
#         'proc_status_dict': Manager().dict()
#     }
    
#     # Generate shared queues and processes for each radar
#     radar_rd_queue_list = []
#     proc_list = []
    
#     print("\nInitializing radars...")
#     for i, RADAR_CFG in enumerate(RADAR_CFG_LIST):
        
#         radar_rd_queue = Manager().Queue()
#         radar_rd_queue_list.append(radar_rd_queue)
#         # Create config for this radar
#         kwargs_CFG = {
#             'RADAR_CFG': RADAR_CFG,
#             'FRAME_EARLY_PROCESSOR_CFG': FRAME_EARLY_PROCESSOR_CFG
#         }
        
#         # Create process for this radar
#         radar_proc = Process(
#             target=radar_proc_method,
#             args=(run_flag, radar_rd_queue, shared_param_dict),
#             kwargs=kwargs_CFG,
#             name=RADAR_CFG['name']
#         )
#         proc_list.append(radar_proc)
    
#     # # Configuration for visualizer and monitor
#     kwargs_CFG = {
#         'VISUALIZER_CFG': VISUALIZER_CFG,
#         'RADAR_CFG_LIST': RADAR_CFG_LIST,
#         'SYNC_MONITOR_CFG': SYNC_MONITOR_CFG,
#         'TRACK_FUSION_CFG': TRACK_FUSION_CFG
#     }
    
#     # # Create visualizer process (fuses tracks and outputs)
#     # print("\nInitializing visualizer...")
#     # vis_proc = Process(
#     #     target=vis_proc_method,
#     #     args=(run_flag, radar_rd_queue_list, shared_param_dict),
#     #     kwargs=kwargs_CFG,
#     #     name='Module_VIS'
#     # )
#     # proc_list.append(vis_proc)
    
#     # # Create monitor process (syncs queues)
#     # print("Initializing sync monitor...")
#     # monitor_proc = Process(
#     #     target=monitor_proc_method,
#     #     args=(run_flag, radar_rd_queue_list, shared_param_dict),
#     #     kwargs=kwargs_CFG,
#     #     name='Module_SCM'
#     # )
#     # proc_list.append(monitor_proc)
    
#     # Create adapter (runs in main thread with GUI)
#     print("Initializing Industrial Visualizer adapter...")
#     adapter = IndustrialVisualizerAdapter(
#         run_flag=run_flag,
#         radar_rd_queue_list=radar_rd_queue_list,
#         shared_param_dict=shared_param_dict,
#         **kwargs_CFG
#     )
    
    
#     # # Initialize process status
#     for proc in proc_list:
#         shared_param_dict['proc_status_dict'][proc.name] = False
    
    
    
    
    
#     # Start all processes
#     print("\n" + "="*70)
#     print("STARTING PROCESSES...")
#     print("="*70)
#     for proc in proc_list:
#         print(f"Starting {proc.name}...")
#         proc.start()
#         sleep(0.5)
    
#     print("\n" + "="*70)
#     print("SYSTEM RUNNING - Press Ctrl+C to stop")
#     print("="*70)
#     # print(f"\nOutput: UDP to {INDUSTRIAL_VIS_CFG['ip_address']}:{INDUSTRIAL_VIS_CFG['port']}")
#     # print("Open Industrial Visualizer to see fused tracks\n")
    
#     # Wait for all processes to finish
#     try:
#         for proc in proc_list:
#             proc.join()
#     except KeyboardInterrupt:
#         print("\n\n" + "="*70)
#         print("STOPPING SYSTEM...")
#         print("="*70)
#         run_flag.value = False
        
#         # Give processes time to cleanup
#         sleep(2)
        
#         # Force terminate if still running
#         for proc in proc_list:
#             if proc.is_alive():
#                 print(f"Force terminating {proc.name}...")
#                 proc.terminate()
#                 proc.join(timeout=1)
    
#     print("\n" + "="*70)
#     print("SYSTEM STOPPED")
#     print("="*70)