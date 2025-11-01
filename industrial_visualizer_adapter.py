"""
Adapter to connect modified thesis code to TI's Industrial Visualizer
Replaces UART parsing, feeds fused tracks directly to GUI
"""

import time
import numpy as np
from queue import Empty

# Logger
import logging
log = logging.getLogger(__name__)


class IndustrialVisualizerAdapter:
    """
    Adapter between your thesis fusion code and TI's Industrial Visualizer GUI
    
    Replaces:
    - UARTParser (no serial reading needed)
    - parseStandardFrame (already parsed in RadarReader)
    
    Keeps:
    - Industrial Visualizer GUI (Window, tabs, 3D plot)
    - PeopleTracking demo class (for display logic)
    """
    
    def __init__(self, run_flag, radar_rd_queue_list, shared_param_dict, **kwargs_CFG):
        """
        Initialize adapter
        """
        self.run_flag = run_flag
        self.radar_rd_queue_list = radar_rd_queue_list
        self.status = shared_param_dict['proc_status_dict']
        self.status['Module_IndViz'] = True
        
        # Config
        self.vis_cfg = kwargs_CFG['VISUALIZER_CFG']
        self.radar_cfg_list = kwargs_CFG['RADAR_CFG_LIST']
        
        # Import track fusion
        from library.track_fusion import TrackFusion
        self.track_fusion = TrackFusion(**kwargs_CFG)
        
        # Statistics
        self.frame_count = 0
        
        # Callback for Industrial Visualizer
        self.update_callback = None
        
        self._log('Industrial Visualizer Adapter initialized')
    
    def set_update_callback(self, callback):
        """
        Set callback function to send data to Industrial Visualizer GUI
        
        Args:
            callback: Function that takes outputDict (Industrial Viz format)
        """
        self.update_callback = callback
        self._log('Update callback registered')
    
    def run(self):
        """
        Main loop: Get fused tracks and send to Industrial Visualizer
        """
        self._log('Starting adapter loop...')
        
        radar_frames_buffer = {cfg['name']: None for cfg in self.radar_cfg_list}
        last_update_time = time.time()
        update_period = 1.0 / 20  # 20 FPS
        
        while self.run_flag.value:
            try:
                # Step 1: Collect frames from all radars (already transformed)
                for i, queue in enumerate(self.radar_rd_queue_list):
                    try:
                        if not queue.empty():
                            frame = queue.get(block=False, timeout=0.001)
                            radar_name = frame['radar_name']
                            radar_frames_buffer[radar_name] = frame
                    except Empty:
                        pass
                
                # Step 2: Check if time to update
                current_time = time.time()
                if current_time - last_update_time >= update_period:
                    available_frames = [f for f in radar_frames_buffer.values() if f is not None]
                    
                    if available_frames:
                        # Step 3: Fuse tracks
                        fused_tracks = self.track_fusion.fuse_tracks(available_frames)
                        
                        if fused_tracks and self.update_callback:
                            # Step 4: Convert to Industrial Visualizer format
                            output_dict = self.convert_to_industrial_viz_format(fused_tracks)
                            
                            # Step 5: Send to GUI via callback
                            self.update_callback(output_dict)
                            
                            self.frame_count += 1
                            
                            if self.frame_count % 100 == 0:
                                self._log(f'Frames: {self.frame_count}, Tracks: {len(fused_tracks)}')
                    
                    last_update_time = current_time
                
                # Small delay
                time.sleep(0.001)
                
            except Exception as e:
                self._log(f'Error in adapter loop: {e}')
                import traceback
                traceback.print_exc()
                time.sleep(0.01)
    
    def convert_to_industrial_viz_format(self, fused_tracks):
        """
        Convert fused tracks to Industrial Visualizer expected format
        
        Industrial Visualizer expects outputDict with:
        {
            'numDetectedObj': int,
            'numDetectedPoints': int,
            'pointCloud': numpy array (N, 5) [x, y, z, doppler, snr],
            'numDetectedTracks': int,
            'trackData': list of track dicts
        }
        
        Args:
            fused_tracks: List of fused track dicts from TrackFusion
        
        Returns:
            outputDict: Dict in Industrial Visualizer format
        """
        output_dict = {}
        
        # Number of tracks
        num_tracks = len(fused_tracks)
        output_dict['numDetectedTracks'] = num_tracks
        output_dict['numDetectedObj'] = num_tracks  # Alias
        
        # Convert tracks to Industrial Visualizer format
        track_data = []
        
        for track in fused_tracks:
            # Industrial Visualizer track format (from PeopleTracking demo)
            viz_track = {
                'tid': track['global_tid'],  # Track ID
                'posX': track['posX'],       # Position X (meters)
                'posY': track['posY'],       # Position Y (meters)
                'posZ': track['posZ'],       # Position Z (meters)
                'velX': track['velX'],       # Velocity X (m/s)
                'velY': track['velY'],       # Velocity Y (m/s)
                'velZ': track['velZ'],       # Velocity Z (m/s)
                'accX': track['accX'],       # Acceleration X (m/s^2)
                'accY': track['accY'],       # Acceleration Y (m/s^2)
                'accZ': track['accZ'],       # Acceleration Z (m/s^2)
                
                # Additional fields that Industrial Viz may use
                'ec': np.zeros(16),          # Error covariance (16 floats)
                'g': track.get('gating_gain', 1.0),  # Gating gain
                'confidenceLevel': track['confidence'],  # Confidence
                
                # Our custom fields (for debugging)
                'num_radars': track.get('num_radars_detected', 1),
                'source_radars': track.get('source_radars', [])
            }
            
            track_data.append(viz_track)
        
        output_dict['trackData'] = track_data
        
        # Point cloud (create synthetic point cloud from tracks for visualization)
        # Industrial Visualizer may display both tracks and point cloud
        point_cloud = []
        for track in fused_tracks:
            # Create a point at track position
            point = [
                track['posX'],
                track['posY'],
                track['posZ'],
                np.sqrt(track['velX']**2 + track['velY']**2 + track['velZ']**2),  # Doppler (speed)
                track['confidence'] * 100  # SNR (fake, use confidence)
            ]
            point_cloud.append(point)
        
        if point_cloud:
            output_dict['pointCloud'] = np.array(point_cloud, dtype=np.float32)
            output_dict['numDetectedPoints'] = len(point_cloud)
        else:
            output_dict['pointCloud'] = np.array([], dtype=np.float32).reshape(0, 5)
            output_dict['numDetectedPoints'] = 0
        
        return output_dict
    
    def _log(self, txt):
        """Print with module name"""
        print(f'[IndVizAdapter]\t{txt}')
    
    def __del__(self):
        """Cleanup on exit"""
        try:
            self._log(f'Closed. Frames: {self.frame_count}')
            if hasattr(self, 'status') and 'Module_IndViz' in self.status:
                self.status['Module_IndViz'] = False
        except (FileNotFoundError, AttributeError, KeyError):
            # Multiprocessing manager already closed, ignore
            pass


class MockUARTParser:
    """
    Mock UART Parser to replace gui_parser.py's UARTParser
    Doesn't read serial, just provides interface compatibility
    """
    
    def __init__(self, adapter):
        """
        Initialize mock parser
        
        Args:
            adapter: IndustrialVisualizerAdapter instance
        """
        self.adapter = adapter
        self.saveBinary = 0
        self.replay = 0
        self.parserType = "MockAdapter"
        self.cliCom = None
        self.dataCom = None
        self.cfg = []
        self.demo = "3D People Tracking"
        self.device = "xWR6843"
        self.comError = 0
        
        # Store latest output dict
        self.latest_output = None
        
        log.info('MockUARTParser initialized (no serial reading)')
    
    def update_output(self, output_dict):
        """
        Called by adapter to update output
        
        Args:
            output_dict: Parsed data in Industrial Viz format
        """
        self.latest_output = output_dict
    
    def readAndParseUartDoubleCOMPort(self):
        """
        Mock method - returns latest output dict instead of reading serial
        """
        if self.latest_output is None:
            # Return empty dict if no data yet
            return {
                'numDetectedTracks': 0,
                'numDetectedObj': 0,
                'numDetectedPoints': 0,
                'pointCloud': np.array([], dtype=np.float32).reshape(0, 5),
                'trackData': []
            }
        
        return self.latest_output
    
    def readAndParseUartSingleCOMPort(self):
        """Mock method - same as double COM port"""
        return self.readAndParseUartDoubleCOMPort()
    
    def setSaveBinary(self, saveBinary):
        """Mock method - compatibility"""
        self.saveBinary = saveBinary
    
    def connectComPorts(self, cliCom, dataCom):
        """Mock method - no actual connection needed"""
        log.info('MockUARTParser: Skipping COM port connection (using adapter)')
    
    def connectComPort(self, cliCom, cliBaud=115200):
        """Mock method - no actual connection needed"""
        log.info('MockUARTParser: Skipping COM port connection (using adapter)')
    
    def sendCfg(self, cfg):
        """Mock method - config already sent by RadarReader"""
        log.info('MockUARTParser: Skipping cfg send (already configured)')
        self.cfg = cfg
    
    def sendLine(self, line):
        """Mock method - compatibility"""
        log.info(f'MockUARTParser: Skipping command send: {line}')


# Helper function to create and start adapter in separate process
def industrial_visualizer_adapter_process(run_flag, radar_rd_queue_list, shared_param_dict, **kwargs_CFG):
    """
    Process function to run adapter
    
    Args:
        run_flag: Shared flag to stop process
        radar_rd_queue_list: List of queues from radars
        shared_param_dict: Shared parameters
        **kwargs_CFG: Configuration dicts
    """
    adapter = IndustrialVisualizerAdapter(
        run_flag=run_flag,
        radar_rd_queue_list=radar_rd_queue_list,
        shared_param_dict=shared_param_dict,
        **kwargs_CFG
    )
    
    adapter.run()