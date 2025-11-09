
import socket
from multiprocessing import Process, Manager
from time import sleep

# Import modified modules
from library.radar_reader_dual_1010 import RadarReader
from library.sync_monitor import SyncMonitor
from library.visualizer import Visualizer
from library.visualizer_dual_tracks import FuseDualRadar

# Choose visualizer type
USE_MATPLOTLIB = False  # Set to False to use UDP output

if USE_MATPLOTLIB:
    from library.visualizer_matplotlib_3d import MatplotlibVisualizer as Visualizer
else:
    from library.visualizer_dual_tracks import FuseDualRadar

# Import configuration
from cfg.config_demo_dual_radar import *

def radar_proc_method(_run_flag, _radar_rd_queue, _shared_param_dict, **_kwargs_CFG):
    """Process for each radar - reads and parses TLV 1010 data"""
    radar = RadarReader(
        run_flag=_run_flag,
        radar_rd_queue=_radar_rd_queue,
        shared_param_dict=_shared_param_dict,
        **_kwargs_CFG
    )
    radar.run()
def fuse_vis_dualradar(_run_flag, _radar_rd_queue_list, vis_queue, _shared_param_dict, **_kwargs_CFG):
    """Fuser process - fuses tracks and outputs to Industrial Visualizer"""
    fuser = FuseDualRadar(
        run_flag=_run_flag,
        radar_rd_queue_list=_radar_rd_queue_list,
        vis_queue=vis_queue,
        shared_param_dict=_shared_param_dict,
        **_kwargs_CFG
    )
    fuser.run()
def vis_proc_method(_run_flag, vis_queue, _shared_param_dict, **_kwargs_CFG):
    """Visualization process - fuses tracks and outputs to Industrial Visualizer"""
    vis = Visualizer(
        run_flag=_run_flag,
        vis_rd_queue=vis_queue,
        shared_param_dict=_shared_param_dict,
        **_kwargs_CFG
    )
    vis.run()
def monitor_proc_method(_run_flag, _radar_rd_queue_list, _shared_param_dict, **_kwargs_CFG):
    """Monitor process - syncs queues between radars"""
    sync = SyncMonitor(
        run_flag=_run_flag,
        radar_rd_queue_list=_radar_rd_queue_list,
        shared_param_dict=_shared_param_dict,
        **_kwargs_CFG
    )
    sync.run()


if __name__ == '__main__':
    print("="*70)
    print("DUAL IWR6843AOP 3D PEOPLE TRACKING SYSTEM")
    print(f"Experiment: {EXPERIMENT_NAME}")
    print(f"Radars: {len(RADAR_CFG_LIST)}")
    print("="*70)
    
    # Generate shared variables between processes
    run_flag = Manager().Value('b', True)
    
    shared_param_dict = {'mansave_flag'       : Manager().Value('c', None),  # set as None, 'image' or 'video', only triggered at the end of recording
                         'autosave_flag'      : Manager().Value('b', False),  # set as False, True or False, constantly high from the beginning to the end of recording
                         'compress_video_file': Manager().Value('c', None),  # the record video file waiting to be compressed
                         'email_image'        : Manager().Value('f', None),  # for image info from save_center to email_notifier module
                         'proc_status_dict'   : Manager().dict(),  # for process status
                         'save_queue'         : Manager().Queue(maxsize=2000)
                         }
    
    # Generate shared queues and processes for each radar
    radar_rd_queue_list = []
    proc_list = []
    
    print("\nInitializing radars...")
    for i, RADAR_CFG in enumerate(RADAR_CFG_LIST):
        
        radar_rd_queue = Manager().Queue() # Queue for radar data has frames dict types
        vis_queue      = Manager().Queue()

        radar_rd_queue_list.append(radar_rd_queue)
        # Create config for this radar
        kwargs_CFG = {
            'RADAR_CFG': RADAR_CFG,
            'FRAME_EARLY_PROCESSOR_CFG': FRAME_EARLY_PROCESSOR_CFG
        }
        # Create process for this radar
        radar_proc = Process(
            target=radar_proc_method,
            args=(run_flag, radar_rd_queue, shared_param_dict),
            kwargs=kwargs_CFG,
            name=RADAR_CFG['name']
        )
        proc_list.append(radar_proc)
    
    # # Configuration for visualizer and monitor
    kwargs_CFG = {'VISUALIZER_CFG'          : VISUALIZER_CFG,
                  'RADAR_CFG_LIST'          : RADAR_CFG_LIST,
                  'MANSAVE_ENABLE'          : MANSAVE_ENABLE,
                  'AUTOSAVE_ENABLE'         : AUTOSAVE_ENABLE,
                  'FRAME_POST_PROCESSOR_CFG': FRAME_POST_PROCESSOR_CFG,
                  'DBSCAN_GENERATOR_CFG'    : DBSCAN_GENERATOR_CFG,
                  'BGNOISE_FILTER_CFG'      : BGNOISE_FILTER_CFG,
                  'HUMAN_TRACKING_CFG'      : HUMAN_TRACKING_CFG,
                  'HUMAN_OBJECT_CFG'        : HUMAN_OBJECT_CFG,
                  'SAVE_CENTER_CFG'         : SAVE_CENTER_CFG,
                  'SYNC_MONITOR_CFG'        : SYNC_MONITOR_CFG
    }
    
    # Create monitor process (syncs queues)
    # print("Initializing sync monitor...")
    # monitor_proc = Process(
    #     target=monitor_proc_method,
    #     args=(run_flag, radar_rd_queue_list, shared_param_dict),
    #     kwargs=kwargs_CFG,
    #     name='Module_SCM'
    # )
    # proc_list.append(monitor_proc)
    
    # Create visualizer process (fuses tracks and outputs)
    
    print("\nInitializing Fuser...")
    fuser_proc = Process(
        target=fuse_vis_dualradar,
        args=(run_flag, radar_rd_queue_list, vis_queue, shared_param_dict),
        kwargs=kwargs_CFG,
        name='Module_FUS'
    )
    proc_list.append(fuser_proc)
    
    
    print("\nInitializing visualizer...")
    vis_proc = Process(
        target=vis_proc_method,
        args=(run_flag, vis_queue, shared_param_dict),
        kwargs=kwargs_CFG,
        name='Module_VIS'
    )
    proc_list.append(vis_proc)
    

    

    
    # # Initialize process status
    for proc in proc_list:
        shared_param_dict['proc_status_dict'][proc.name] = False
    
    # Start all processes
    print("\n" + "="*70)
    print("STARTING PROCESSES...")
    print("="*70)
    for proc in proc_list:
        print(f"Starting {proc.name}...")
        proc.start()
        sleep(0.5)
    
    print("\n" + "="*70)
    print("SYSTEM RUNNING - Press Ctrl+C to stop")
    print("="*70)
    # print(f"\nOutput: UDP to {INDUSTRIAL_VIS_CFG['ip_address']}:{INDUSTRIAL_VIS_CFG['port']}")
    # print("Open Industrial Visualizer to see fused tracks\n")
    
    # Wait for all processes to finish
    try:
        for proc in proc_list:
            proc.join()
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("STOPPING SYSTEM...")
        print("="*70)
        run_flag.value = False
        
        # Give processes time to cleanup
        sleep(2)
        
        # Force terminate if still running
        for proc in proc_list:
            if proc.is_alive():
                print(f"Force terminating {proc.name}...")
                proc.terminate()
                proc.join(timeout=1)
    
    print("\n" + "="*70)
    print("SYSTEM STOPPED")
    print("="*70)