# """
# Modified RadarReader for dual IWR6843AOP with TLV 1010 (3D People Tracking)
# Parses only tracker output (no point cloud)
# """

# import struct
# import time
# from datetime import datetime
# import numpy as np
# import serial

# from library.frame_early_processor import FrameEProcessor

# # TLV Header constants
# MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
# HEADER_LENGTH = 40  # bytes (8 magic + 32 header info)

# # TLV Types for 3D People Tracking
# TLV_TYPE_TRACKER_PROC_TARGET_LIST = 1010  # 3D target list


# class RadarReader:
#     def __init__(self, run_flag, radar_rd_queue, shared_param_dict, **kwargs_CFG):
#         """
#         Initialize radar reader for TLV 1010 parsing
#         """
#         self.run_flag = run_flag
#         self.radar_rd_queue = radar_rd_queue
#         self.status = shared_param_dict['proc_status_dict']
        
#         # Get radar config
#         RDR_CFG = kwargs_CFG['RADAR_CFG']
#         self.name = RDR_CFG['name']
#         self.cfg_port_name = RDR_CFG['cfg_port_name']
#         self.data_port_name = RDR_CFG['data_port_name']
#         self.cfg_file_name = RDR_CFG['cfg_file_name']
        
#         self.status[self.name] = True
        
#         # Frame early processor for coordinate transformation
#         self.fep = FrameEProcessor(**kwargs_CFG)
        
#         self.cfg_port = None
#         self.data_port = None
        
#         # Statistics
#         self.frame_count = 0
#         self.parse_errors = 0
        
#         self._log('Initialized for TLV 1010 (3D Tracker)')

#     def connect(self) -> bool:
#         """Connect to radar COM ports"""
#         try:
#             self.cfg_port = serial.Serial(self.cfg_port_name, baudrate=115200, timeout=1)
#             self.data_port = serial.Serial(self.data_port_name, baudrate=921600, timeout=1)
            
#             if not (self.cfg_port.is_open and self.data_port.is_open):
#                 raise serial.SerialException("Ports not opened")
            
#             self._log(f'Connected: CFG={self.cfg_port_name}, DATA={self.data_port_name}')
            
#             # Send configuration (optional - radar should already be configured)
#             # self._send_cfg(self._read_cfg(self.cfg_file_name), self.cfg_port)
            
#             return True
            
#         except serial.SerialException as e:
#             self._log(f'Connection failed: {e}')
#             return False

#     def run(self):
#         """Main loop - read and parse TLV 1010 frames"""
#         if not self.connect():
#             self._log(f"Radar {self.name} Connection Failed")
#             self.run_flag.value = False
#             return

#         data_buffer = b''
        
#         self._log('Starting data acquisition...')
        
#         while self.run_flag.value:
#             try:
#                 # Read available data
#                 bytes_available = self.data_port.in_waiting
#                 if bytes_available > 0:
#                     data_buffer += self.data_port.read(bytes_available)
                
#                 # Look for complete frame (at least 2 magic words)
#                 if data_buffer.count(MAGIC_WORD) >= 2:
#                     # Find first magic word
#                     start_idx = data_buffer.find(MAGIC_WORD)
#                     if start_idx == -1:
#                         continue
                    
#                     # Extract frame starting from magic word
#                     frame_data = data_buffer[start_idx:]
                    
#                     # Try to parse the frame
#                     tracks, frame_length = self._parse_tlv_1010_frame(frame_data)
                    
#                     if tracks is not None and len(tracks) > 0:
#                         # Apply coordinate transformation
#                         transformed_tracks = self._transform_tracks(tracks)
                        
#                         # Put into queue
#                         self.radar_rd_queue.put({
#                             'radar_name': self.name,
#                             'frame_number': self.frame_count,
#                             'num_tracks': len(transformed_tracks),
#                             'tracks': transformed_tracks,
#                             'timestamp': time.time()
#                         })
                        
#                         self.frame_count += 1
                        
#                         if self.frame_count % 100 == 0:
#                             self._log(f'Frames: {self.frame_count}, Errors: {self.parse_errors}')
                    
#                     # Remove processed frame from buffer
#                     if frame_length > 0:
#                         data_buffer = data_buffer[start_idx + frame_length:]
#                     else:
#                         # Remove just the first magic word to continue searching
#                         data_buffer = data_buffer[start_idx + len(MAGIC_WORD):]
                
#                 # Prevent buffer overflow
#                 if len(data_buffer) > 100000:
#                     self._log(f'Warning: Buffer overflow, clearing. Size: {len(data_buffer)}')
#                     data_buffer = b''
                    
#             except Exception as e:
#                 self._log(f'Error in main loop: {e}')
#                 self.parse_errors += 1
#                 time.sleep(0.01)

#     def _parse_tlv_1010_frame(self, data):
#         """
#         Parse a single frame containing TLV 1010
#         Returns: (tracks_array, frame_length) or (None, 0) on error
#         """
#         try:
#             if len(data) < HEADER_LENGTH:
#                 return None, 0
            
#             # Parse header (40 bytes after magic word)
#             header = data[8:HEADER_LENGTH]
            
#             # Unpack header fields
#             version = struct.unpack('I', header[0:4])[0]
#             total_packet_len = struct.unpack('I', header[4:8])[0]
#             platform = struct.unpack('I', header[8:12])[0]
#             frame_number = struct.unpack('I', header[12:16])[0]
#             time_cpu_cycles = struct.unpack('I', header[16:20])[0]
#             num_detected_obj = struct.unpack('I', header[20:24])[0]
#             num_tlvs = struct.unpack('I', header[24:28])[0]
#             subframe_number = struct.unpack('I', header[28:32])[0]
            
#             # Check if we have enough data
#             if len(data) < total_packet_len:
#                 return None, 0
            
#             # Parse TLVs
#             tlv_start = HEADER_LENGTH
#             tracks = []
            
#             for _ in range(num_tlvs):
#                 if tlv_start + 8 > len(data):
#                     break
                
#                 # Parse TLV header
#                 tlv_type = struct.unpack('I', data[tlv_start:tlv_start+4])[0]
#                 tlv_length = struct.unpack('I', data[tlv_start+4:tlv_start+8])[0]
#                 tlv_data_start = tlv_start + 8
                
#                 # Check for TLV 1010 (3D Target List)
#                 if tlv_type == TLV_TYPE_TRACKER_PROC_TARGET_LIST:
#                     tracks = self._parse_tlv_1010_data(data[tlv_data_start:tlv_data_start+tlv_length])
                
#                 tlv_start = tlv_data_start + tlv_length
            
#             return tracks, total_packet_len
            
#         except Exception as e:
#             self._log(f'Parse error: {e}')
#             self.parse_errors += 1
#             return None, 0

#     def _parse_tlv_1010_data(self, tlv_data):
#         """
#         Parse TLV 1010: 3D Target List
#         Each target: 112 bytes
#         Structure per target:
#             - tid (uint32): 4 bytes
#             - posX, posY, posZ (float): 12 bytes
#             - velX, velY, velZ (float): 12 bytes
#             - accX, accY, accZ (float): 12 bytes
#             - ec[16] (float): 64 bytes (covariance matrix)
#             - g (float): 4 bytes (gating gain)
#             - confidenceLevel (float): 4 bytes
#         """
#         TARGET_SIZE = 112  # bytes per target
#         num_targets = len(tlv_data) // TARGET_SIZE
        
#         tracks = []
        
#         for i in range(num_targets):
#             offset = i * TARGET_SIZE
#             target_data = tlv_data[offset:offset + TARGET_SIZE]
            
#             if len(target_data) < TARGET_SIZE:
#                 break
            
#             try:
#                 # Unpack target data
#                 tid = struct.unpack('I', target_data[0:4])[0]
                
#                 # Position (meters)
#                 posX = struct.unpack('f', target_data[4:8])[0]
#                 posY = struct.unpack('f', target_data[8:12])[0]
#                 posZ = struct.unpack('f', target_data[12:16])[0]
                
#                 # Velocity (m/s)
#                 velX = struct.unpack('f', target_data[16:20])[0]
#                 velY = struct.unpack('f', target_data[20:24])[0]
#                 velZ = struct.unpack('f', target_data[24:28])[0]
                
#                 # Acceleration (m/s^2)
#                 accX = struct.unpack('f', target_data[28:32])[0]
#                 accY = struct.unpack('f', target_data[32:36])[0]
#                 accZ = struct.unpack('f', target_data[36:40])[0]
                
#                 # Error covariance matrix (16 floats) - skip for now
#                 # ec = struct.unpack('16f', target_data[40:104])
                
#                 # Gating gain
#                 g = struct.unpack('f', target_data[104:108])[0]
                
#                 # Confidence level
#                 confidence = struct.unpack('f', target_data[108:112])[0]
                
#                 # Create track dictionary
#                 track = {
#                     'tid': tid,
#                     'posX': posX,
#                     'posY': posY,
#                     'posZ': posZ,
#                     'velX': velX,
#                     'velY': velY,
#                     'velZ': velZ,
#                     'accX': accX,
#                     'accY': accY,
#                     'accZ': accZ,
#                     'gating_gain': g,
#                     'confidence': confidence
#                 }
                
#                 tracks.append(track)
                
#             except Exception as e:
#                 self._log(f'Error parsing target {i}: {e}')
#                 continue
        
#         return tracks

#     def _transform_tracks(self, tracks):
#         """
#         Apply coordinate transformation to tracks based on radar position/orientation
#         Uses the FrameEProcessor for rotation and translation
#         """
#         transformed_tracks = []
        
#         for track in tracks:
#             # Extract position as numpy array
#             pos = np.array([[track['posX'], track['posY'], track['posZ']]], dtype=np.float32)
#             vel = np.array([[track['velX'], track['velY'], track['velZ']]], dtype=np.float32)
            
#             # Apply rotation
#             pos_rotated = self.fep.FEP_trans_rotation_3D(pos)
#             vel_rotated = self.fep.FEP_trans_rotation_3D(vel)  # Velocity also needs rotation
            
#             # Apply translation
#             pos_transformed = self.fep.FEP_trans_position_3D(pos_rotated)
#             # Velocity doesn't need translation (it's a vector, not a point)
            
#             # Create transformed track
#             transformed_track = track.copy()
#             transformed_track['posX'] = pos_transformed[0, 0]
#             transformed_track['posY'] = pos_transformed[0, 1]
#             transformed_track['posZ'] = pos_transformed[0, 2]
#             transformed_track['velX'] = vel_rotated[0, 0]
#             transformed_track['velY'] = vel_rotated[0, 1]
#             transformed_track['velZ'] = vel_rotated[0, 2]
            
#             transformed_tracks.append(transformed_track)
        
#         return transformed_tracks

#     def _read_cfg(self, cfg_file_name):
#         """Read radar configuration file"""
#         cfg_list = []
#         try:
#             with open(cfg_file_name) as f:
#                 lines = f.read().split('\n')
#             for line in lines:
#                 line = line.strip()
#                 if line and not line.startswith('%'):
#                     cfg_list.append(line)
#         except Exception as e:
#             self._log(f'Error reading config: {e}')
#         return cfg_list

#     def _send_cfg(self, cfg_list, cfg_port):
#         """Send configuration commands to radar"""
#         for line in cfg_list:
#             try:
#                 cfg_port.write((line + '\n').encode())
#                 time.sleep(0.05)
                
#                 # Read response
#                 response = b''
#                 timeout = time.time() + 1
#                 while time.time() < timeout:
#                     if cfg_port.in_waiting > 0:
#                         response += cfg_port.read(cfg_port.in_waiting)
#                         break
#                     time.sleep(0.01)
                
#                 self._log(f'CFG: {line[:50]}... -> {response.decode("utf-8", errors="ignore").strip()}')
                
#             except Exception as e:
#                 self._log(f'Config send error: {e}')

#     def _log(self, txt):
#         """Print with radar name prefix"""
#         print(f'[{self.name}]\t{txt}')

#     def __del__(self):
#         """Cleanup on exit"""
#         try:
#             if self.cfg_port and self.cfg_port.is_open:
#                 self.cfg_port.write(b'sensorStop\n')
#                 time.sleep(0.1)
#                 self.cfg_port.close()
#             if self.data_port and self.data_port.is_open:
#                 self.data_port.close()
#         except:
#             pass
        
#         self._log(f"Closed. Frames: {self.frame_count}, Errors: {self.parse_errors}")
#         self._log(f"Timestamp: {datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}")
        
#         if self.name in self.status:
#             self.status[self.name] = False