"""
Config file for Dual IWR6843AOP with SERIAL OUTPUT to TI Industrial Visualizer
Uses virtual serial port for communication
"""

# global save parameters
EXPERIMENT_NAME = 'dual_radar_tracking'
RADAR_FPS = 20  # 20 frames per second

# Save settings
MANSAVE_ENABLE = False
MANSAVE_PERIOD = 30

AUTOSAVE_ENABLE = False
AUTOSAVE_PERIOD = 600

# =============================================================================
# DUAL RADAR CONFIGURATION
# =============================================================================
RADAR_CFG_LIST = [
    {
        'name'          : 'IWR6843_Radar1',
        'cfg_port_name' : '/dev/ttyUSB0',      # ⚠️ UPDATE: Your radar's config port
        'data_port_name': '/dev/ttyUSB1',      # ⚠️ UPDATE: Your radar's data port
        'cfg_file_name' : './cfg/AOP_6m_default.cfg',
        
        # Coordinate transformation
        'pos_offset'    : (0, 0, 2.5),         # (x, y, z) in meters
        'facing_angle'  : {
            'angle': (-20, 0, 0),              # (pitch, yaw, roll) in degrees
            'sequence': 'zyx'
        },
        
        # Boundary limits
        'xlim'          : (-2, 2),
        'ylim'          : (0.2, 4.1),
        'zlim'          : (0, 3.7),
        
        'ES_threshold'  : {'range': (0, None), 'speed_none_0_exception': False},
    },
    
    # Radar 2 - Uncomment when ready
    # {
    #     'name'          : 'IWR6843_Radar2',
    #     'cfg_port_name' : 'COM5',
    #     'data_port_name': 'COM6',
    #     'cfg_file_name' : './cfg/IWR6843_3D_20fps.cfg',
    #     'pos_offset'    : (4, 0, 2.5),
    #     'facing_angle'  : {'angle': (0, -45, 0), 'sequence': 'zyx'},
    #     'xlim'          : (-3, 3),
    #     'ylim'          : (0.5, 8),
    #     'zlim'          : (0, 3),
    #     'ES_threshold'  : {'range': (0, None), 'speed_none_0_exception': False},
    # },
]

# =============================================================================
# TI INDUSTRIAL VISUALIZER - SERIAL OUTPUT CONFIG
# =============================================================================
INDUSTRIAL_VIS_CFG = {
    'enable'          : True,
    
    # SERIAL PORT SETTINGS (not UDP!)
    'serial_port'     : '/tmp/ttyV0',              # ⚠️ UPDATE: Virtual COM port (WRITE side)
    'baud_rate'       : 921600,               # Standard TI baud rate (921600)
    
    # Notes:
    # - Create virtual serial port pair (e.g., COM20 <-> COM21)
    # - Your code writes to COM20
    # - Industrial Visualizer reads from COM21
}

# =============================================================================
# VISUALIZER CONFIG
# =============================================================================
VISUALIZER_CFG = {
    'dimension'               : '3D',
    'VIS_xlim'                : (-2, 2),
    'VIS_ylim'                : (0.3, 4),
    'VIS_zlim'                : (0, 3.7),
    'auto_inactive_skip_frame': 0,
    'output_format'           : 'serial',
    'output_port'             : 5000,
}

# =============================================================================
# TRACK FUSION CONFIG
# =============================================================================
TRACK_FUSION_CFG = {
    'enable'                  : True,
    'distance_threshold'      : 0.5,          # meters
    'confidence_weight'       : 0.7,
    'velocity_weight'         : 0.3,
    'fusion_method'           : 'weighted_average',
}

# =============================================================================
# OTHER CONFIGS (keep for compatibility)
# =============================================================================
SYNC_MONITOR_CFG = {
    'rd_qsize_warning': 5,
    'sc_qsize_warning': 20,
}

FRAME_EARLY_PROCESSOR_CFG = {
    'FEP_frame_deque_length': 1,
}

FRAME_POST_PROCESSOR_CFG = {
    'FPP_global_xlim' : (-5, 5),
    'FPP_global_ylim' : (0, 10),
    'FPP_global_zlim' : (0.1, 3),
    'track_fusion_distance_threshold': 0.5,
    'track_id_offset'                : 1000,
}

DBSCAN_GENERATOR_CFG = {'Default': {}}
BGNOISE_FILTER_CFG = {'BGN_enable': False}
HUMAN_TRACKING_CFG = {'TRK_enable': False}
HUMAN_OBJECT_CFG = {}
SAVE_CENTER_CFG = {
    'file_save_dir'      : f'./data/{EXPERIMENT_NAME}/',
    'experiment_name'    : EXPERIMENT_NAME,
    'mansave_period'     : MANSAVE_PERIOD,
    'mansave_rdr_frame_max': int(MANSAVE_PERIOD * RADAR_FPS * 1.2),
}
CAMERA_CFG = {}
EMAIL_NOTIFIER_CFG = {}