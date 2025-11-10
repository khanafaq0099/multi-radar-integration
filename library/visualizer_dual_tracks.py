"""
Fuser for Dual Radar System - Track Fusion & Serial Output to TI Industrial Visualizer
Collects tracks from both radars, fuses them, and outputs via VIRTUAL SERIAL PORT
"""

import serial
import struct
import time
from datetime import datetime
import numpy as np

from library.track_fusion import TrackFusion


class FuseDualRadar:
    def __init__(self, run_flag, radar_rd_queue_list, vis_queue, shared_param_dict, **kwargs_CFG):
        """
        Initialize fuser for dual radar with SERIAL output to Industrial Visualizer
        """
        self.run_flag = run_flag
        self.radar_rd_queue_list = radar_rd_queue_list
        self.vis_queue = vis_queue
        self.status = shared_param_dict['proc_status_dict']
        self.status['Module_FUS'] = True
        
        # Config
        self.vis_cfg = kwargs_CFG['VISUALIZER_CFG']
        self.radar_cfg_list = kwargs_CFG['RADAR_CFG_LIST']
        self.ind_vis_cfg = kwargs_CFG.get('INDUSTRIAL_VIS_CFG', {})
        
        # Track fusion
        self.track_fusion = TrackFusion(**kwargs_CFG)
        
        # Serial port for Industrial Visualizer
        self.serial_port = None
        self._setup_serial()
        
        # Statistics
        self.frame_count = 0
        self.total_tracks_processed = 0
        self.last_print_time = time.time()
        
        self._log('Fuser initialized with SERIAL output to Industrial Visualizer')

    def _setup_serial(self):
        """Setup virtual serial port for Industrial Visualizer"""
        if not self.ind_vis_cfg.get('enable', True):
            self._log('Industrial Visualizer output disabled')
            return
        
        try:
            port_name = self.ind_vis_cfg.get('serial_port', '/tmp/ttyV0')  # Virtual COM port
            baud_rate = self.ind_vis_cfg.get('baud_rate', 921600)     # TI standard baud
            
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            self.serial_port.reset_output_buffer()
            self._log(f'Serial port {port_name} opened at {baud_rate} baud')
            
        except Exception as e:
            self._log(f'Serial port setup error: {e}')
            self._log('Make sure virtual serial port is created (use com0com on Windows or socat on Linux)')
            self.serial_port = None

    def run(self):
        """
        Main loop - collect frames from both radars, fuse tracks, and output to Serial
        """
        if not self.serial_port:
            self._log('ERROR: Serial port not available. System cannot start.')
            self._log('Create a virtual serial port pair first!')
            self.run_flag.value = False
            return
        
        self._log('Starting fusion and serial output loop...')
        self._log(f'Output: SERIAL to {self.ind_vis_cfg.get("serial_port")}')
        self._log('Configure Industrial Visualizer to read from the paired COM port')
        
        radar_frames_buffer = {cfg['name']: None for cfg in self.radar_cfg_list}
        last_output_time = time.time()
        output_period = 1.0 / 20  # 20 FPS output
        
        while self.run_flag.value:
            try:
                # Collect frames from all radars
                for i, queue in enumerate(self.radar_rd_queue_list):
                    if not queue.empty():
                        frame = queue.get(block=False)
                        radar_name = frame['radar_name']
                        radar_frames_buffer[radar_name] = frame
                
                # Check if it's time to process and output
                current_time = time.time()
                if current_time - last_output_time >= output_period:
                    # Get all available frames
                    available_frames = [f for f in radar_frames_buffer.values() if f is not None]
                    
                    if available_frames:
                        # Fuse tracks from all radars
                        fused_tracks = self.track_fusion.fuse_tracks(available_frames)
                        
                        if fused_tracks:
                            # Output to Industrial Visualizer via Serial
                            self._output_to_serial(fused_tracks)
                            
                            # Also send to matplotlib visualizer queue if needed
                            try:
                                self.vis_queue.put_nowait(fused_tracks)
                            except:
                                pass  # Queue full, skip
                            
                            # Update statistics
                            self.total_tracks_processed += len(fused_tracks)
                            self.frame_count += 1
                            
                            # Print periodic status
                            if current_time - self.last_print_time > 2.0:
                                self._log(f'Frames: {self.frame_count}, '
                                         f'Current tracks: {len(fused_tracks)}, '
                                         f'Total processed: {self.total_tracks_processed}')
                                self.last_print_time = current_time
                    
                    last_output_time = current_time
                
                # Small delay to prevent CPU spinning
                time.sleep(0.001)
                
            except Exception as e:
                self._log(f'Error in main loop: {e}')
                import traceback
                traceback.print_exc()
                time.sleep(0.01)

    def _output_to_serial(self, fused_tracks):
        """
        Send fused tracks to Industrial Visualizer via Serial Port
        Format: TLV 1010 structure compatible with TI Industrial Visualizer
        """
        if not self.serial_port:
            return
        
        try:
            # Build TLV packet for Industrial Visualizer
            # Magic word for TI mmWave radar frames
            MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
            
            # Build TLV 1010 data (3D Target List)
            tlv_data = self._build_tlv_1010(fused_tracks)
            
            # TLV header: type (4 bytes) + length (4 bytes)
            tlv_type = struct.pack('<I', 1010)  # TLV type 1010
            tlv_length = struct.pack('<I', len(tlv_data))
            
            # Calculate total packet length
            total_length = 40 + 8 + len(tlv_data)  # header(40) + tlv_header(8) + tlv_data
            
            # Frame header (40 bytes total after magic word)
            version = struct.pack('<I', 0xA1642333)  # SDK version
            total_packet_len = struct.pack('<I', total_length)
            platform = struct.pack('<I', 0xA6843)  # IWR6843AOP platform ID
            frame_number = struct.pack('<I', self.frame_count)
            time_cpu = struct.pack('<I', int(time.time() * 1000) & 0xFFFFFFFF)
            num_detected = struct.pack('<I', len(fused_tracks))
            num_tlvs = struct.pack('<I', 1)  # Only TLV 1010
            subframe = struct.pack('<I', 0)
            
            # Assemble complete packet
            packet = (MAGIC_WORD + 
                     version + total_packet_len + platform + 
                     frame_number + time_cpu + num_detected + num_tlvs + subframe +
                     tlv_type + tlv_length + 
                     tlv_data)
            
            # Send via serial port
            self.serial_port.write(packet)
            self.serial_port.flush()  # Ensure data is transmitted immediately
            
        except Exception as e:
            self._log(f'Serial output error: {e}')

    def _build_tlv_1010(self, fused_tracks):
        """
        Build TLV 1010 binary data from fused tracks
        
        TLV 1010 Format (3D People Tracking Target List):
        Each track: 112 bytes total
        - TID (4 bytes, uint32)
        - posX, posY, posZ (12 bytes, 3 floats)
        - velX, velY, velZ (12 bytes, 3 floats)
        - accX, accY, accZ (12 bytes, 3 floats)
        - EC (error covariance, 64 bytes, 16 floats) - 4x4 matrix
        - G (gating gain, 4 bytes, float)
        - Confidence level (4 bytes, float)
        """
        tlv_data = b''
        
        for track in fused_tracks:
            # Track ID (use global_tid)
            tid = struct.pack('<I', track.get('global_tid', 0))
            
            # Position (X, Y, Z)
            posX = struct.pack('<f', track['posX'])
            posY = struct.pack('<f', track['posY'])
            posZ = struct.pack('<f', track['posZ'])
            
            # Velocity (X, Y, Z)
            velX = struct.pack('<f', track['velX'])
            velY = struct.pack('<f', track['velY'])
            velZ = struct.pack('<f', track['velZ'])
            
            # Acceleration (X, Y, Z)
            accX = struct.pack('<f', track['accX'])
            accY = struct.pack('<f', track['accY'])
            accZ = struct.pack('<f', track['accZ'])
            
            # Error covariance matrix (16 floats = 64 bytes)
            # For fused tracks, use identity matrix scaled by confidence
            conf = track.get('confidence', 0.5)
            ec_scale = (1.0 - conf) * 0.1  # Lower confidence = higher uncertainty
            
            # 4x4 covariance matrix (position + velocity covariance)
            ec = struct.pack('<16f',
                ec_scale, 0, 0, 0,           # posX variance
                0, ec_scale, 0, 0,           # posY variance
                0, 0, ec_scale, 0,           # posZ variance
                0, 0, 0, ec_scale * 0.5      # vel variance
            )
            
            # Gating gain (measure of track quality)
            g = struct.pack('<f', track.get('gating_gain', 1.0))
            
            # Confidence level (0-1)
            confidence = struct.pack('<f', track['confidence'])
            
            # Combine into single track (112 bytes)
            track_data = (tid + 
                         posX + posY + posZ + 
                         velX + velY + velZ + 
                         accX + accY + accZ + 
                         ec + 
                         g + 
                         confidence)
            
            # Verify size
            if len(track_data) != 112:
                self._log(f'Warning: Track data size mismatch: {len(track_data)} bytes')
            
            tlv_data += track_data
        
        return tlv_data

    def _log(self, txt):
        """Print with module name"""
        print(f'[Fuser]\t{txt}')

    def __del__(self):
        """Cleanup on exit"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
        except:
            pass
        
        self._log(f'Closed. Frames: {self.frame_count}, '
                 f'Total tracks: {self.total_tracks_processed}')
        self._log(f"Timestamp: {datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}")
        
        if 'Module_FUS' in self.status:
            self.status['Module_FUS'] = False


if __name__ == '__main__':
    # Test fuser with Serial output
    from multiprocessing import Manager
    
    run_flag = Manager().Value('b', True)
    queue1 = Manager().Queue()
    queue2 = Manager().Queue()
    vis_queue = Manager().Queue()
    shared_dict = {'proc_status_dict': Manager().dict()}
    
    # Test config
    kwargs_CFG = {
        'VISUALIZER_CFG': {
            'dimension': '3D',
            'VIS_xlim': (-5, 5),
            'VIS_ylim': (0, 10),
            'VIS_zlim': (0, 3)
        },
        'RADAR_CFG_LIST': [
            {'name': 'Radar1', 'pos_offset': (0, 0, 2.5)},
            {'name': 'Radar2', 'pos_offset': (4, 0, 2.5)}
        ],
        'TRACK_FUSION_CFG': {
            'distance_threshold': 0.5
        },
        'INDUSTRIAL_VIS_CFG': {
            'enable': True,
            'serial_port': 'COM20',  # Virtual COM port (write side)
            'baud_rate': 921600      # Standard TI baud rate
        }
    }
    
    fuser = FuseDualRadar(run_flag, [queue1, queue2], vis_queue, shared_dict, **kwargs_CFG)
    
    # Simulate test data
    test_frame1 = {
        'radar_name': 'Radar1',
        'timestamp': time.time(),
        'num_tracks': 1,
        'tracks': [
            {'tid': 1, 'posX': 1.0, 'posY': 2.0, 'posZ': 1.5,
             'velX': 0.1, 'velY': 0.2, 'velZ': 0.0,
             'accX': 0.0, 'accY': 0.0, 'accZ': 0.0,
             'confidence': 0.9, 'gating_gain': 1.0}
        ]
    }
    
    queue1.put(test_frame1)
    
    print("Fuser test - sending to Industrial Visualizer via Serial")
    print("Setup virtual COM port pair first!")
    print("Press Ctrl+C to stop")
    
    try:
        fuser.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        run_flag.value = False