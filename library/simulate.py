#!/usr/bin/env python3
"""
simulate_real_radar.py

Simulates feeding real radar track frames into the dual-radar fuser/visualizer.
Works in two modes:
  1) --csv <path>  : read frames from a CSV file (columns documented below)
  2) --synthetic   : generate synthetic moving tracks for testing

It uses your uploaded modules:
  - track_fusion.py  (TrackFusion)
  - visualizer_dual_tracks.py (FuseDualRadar)

Place this file in the same folder as those modules or point PYTHONPATH accordingly.
"""

import argparse
import time
import sys
import os
from multiprocessing import Process, Manager
import queue
import csv
import random

# Ensure current folder is on path so we import your local files
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.insert(0, here)

# Import your classes (adjust if your project package layout differs)
# visualizer_dual_tracks.py imports TrackFusion internally; we import the visualizer class.
try:
    from visualizer_dual_tracks import FuseDualRadar
    # note: visualizer_dual_tracks imports TrackFusion inside so the module will be used.
except Exception as e:
    print("Error importing visualizer_dual_tracks.FuseDualRadar:", e)
    raise

# ---------------------------
# CSV format expected
# ---------------------------
# CSV must contain rows representing a single radar *track* observation.
# Required columns:
#   frame_id,timestamp,radar_name,tid,posX,posY,posZ,velX,velY,velZ,accX,accY,accZ,confidence
#
# Each CSV row is one track. Rows with the same frame_id and radar_name are grouped into a single frame.
# timestamp can be a float (seconds epoch) or relative seconds; if empty, script will set time.time()
#
# Example row:
#  1,1699990000.123,Radar1,1,1.0,2.0,1.5,0.1,0.2,0.0,0.0,0.0,0.0,0.9
#
# Note: the visualizer code expects a dict frame:
#  {
#    'radar_name': 'Radar1',
#    'timestamp': <float>,
#    'frame_id': <int>,
#    'tracks': [ { 'tid':..., 'posX':..., 'posY':..., 'posZ':..., ... }, ... ]
#  }
#
# ---------------------------

def read_csv_to_frames(csv_path):
    """Read CSV and group rows into frames per radar_name+frame_id"""
    frames = {}
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Required fields
            frame_id = r.get('frame_id') or r.get('frame') or r.get('frameId')
            timestamp = r.get('timestamp') or ''
            radar_name = r.get('radar_name') or r.get('radar') or r.get('radarName')
            if not frame_id or not radar_name:
                continue
            key = (radar_name, int(frame_id))
            if key not in frames:
                frames[key] = {
                    'radar_name': radar_name,
                    'timestamp': float(timestamp) if timestamp else time.time(),
                    'frame_id': int(frame_id),
                    'tracks': []
                }

            # Build track dict, convert numerical fields
            def safef(k, default=0.0):
                val = r.get(k, '')
                return float(val) if val != '' else default

            track = {
                'tid': int(r.get('tid', 0)),
                'posX': safef('posX'),
                'posY': safef('posY'),
                'posZ': safef('posZ'),
                'velX': safef('velX'),
                'velY': safef('velY'),
                'velZ': safef('velZ'),
                'accX': safef('accX'),
                'accY': safef('accY'),
                'accZ': safef('accZ'),
                'confidence': safef('confidence', 0.5)
            }
            frames[key]['tracks'].append(track)

    # Return list of frames grouped by time order (sort by frame_id)
    frames_list = sorted(frames.values(), key=lambda x: (x['radar_name'], x['frame_id']))
    return frames_list


def synthetic_generator(n_frames=200, n_objects=2, radar_names=('Radar1','Radar2')):
    """Yield simulated frames for each radar per frame index.
       Objects move in straight lines; radars observe them with slight offsets/noise.
    """
    # init object states (posX,posY,posZ, velX,velY)
    objs = []
    for i in range(n_objects):
        x = random.uniform(-1.0, 1.0) + i*1.0
        y = random.uniform(1.0, 4.0)
        z = random.uniform(0.5, 1.5)
        vx = random.uniform(-0.1, 0.1)
        vy = random.uniform(-0.05, 0.05)
        objs.append({'posX': x, 'posY': y, 'posZ': z, 'velX': vx, 'velY': vy, 'tid': i+1})

    for f in range(n_frames):
        timestamp = time.time()
        frames = []
        # update object positions
        for o in objs:
            o['posX'] += o['velX']
            o['posY'] += o['velY']
            # small random accel
            o['velX'] += random.uniform(-0.01, 0.01)
            o['velY'] += random.uniform(-0.005, 0.005)

        # create per-radar observations (with detection dropouts & noise)
        for rname in radar_names:
            tracks = []
            for o in objs:
                # random miss probability
                if random.random() < 0.05:
                    continue
                noise = lambda: random.gauss(0, 0.02)  # 2cm std dev
                posX = o['posX'] + noise()
                posY = o['posY'] + noise()
                posZ = o['posZ'] + noise()
                velX = o['velX'] + random.gauss(0, 0.01)
                velY = o['velY'] + random.gauss(0, 0.01)
                track = {
                    'tid': o['tid'] + (0 if rname == radar_names[0] else 1000),  # different local tids per radar
                    'posX': posX, 'posY': posY, 'posZ': posZ,
                    'velX': velX, 'velY': velY, 'velZ': 0.0,
                    'accX': 0.0, 'accY': 0.0, 'accZ': 0.0,
                    'confidence': random.uniform(0.6, 0.95)
                }
                tracks.append(track)

            frame = {
                'radar_name': rname,
                'timestamp': timestamp,
                'frame_id': f,
                'tracks': tracks
            }
            frames.append(frame)

        yield frames
        time.sleep(0.02)  # emulate ~50 Hz sensor rate


def feeder_from_frames(frames_seq, queues_by_name, delay=0.0):
    """Push frames (list of frames for multiple radars) to manager queues"""
    # queues_by_name: dict radar_name -> Manager.Queue
    for frames in frames_seq:
        # frames is either a list of multiple radar frames or single frame
        if isinstance(frames, dict):
            frames = [frames]
        for frame in frames:
            rname = frame['radar_name']
            q = queues_by_name.get(rname)
            if q is None:
                print(f"[Feeder] No queue for radar {rname}, skipping")
                continue
            q.put(frame)
        if delay:
            time.sleep(delay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', help='CSV file containing tracks (see format in header)', default=None)
    ap.add_argument('--synthetic', action='store_true', help='Run synthetic generator if no CSV given')
    ap.add_argument('--frames', type=int, default=500, help='Number of frames (synthetic mode)')
    ap.add_argument('--radars', nargs='+', default=['Radar1', 'Radar2'], help='List of radar names')
    args = ap.parse_args()

    manager = Manager()
    run_flag = manager.Value('b', True)
    # Create manager queues, one per radar
    queues = [manager.Queue() for _ in args.radars]
    radar_rd_queue_list = queues  # matches the visualizer constructor signature
    shared_dict = {'proc_status_dict': manager.dict()}

    # Prepare kwargs_CFG similar to your test in visualizer_dual_tracks
    kwargs_CFG = {
        'VISUALIZER_CFG': {
            'dimension': '3D',
            'VIS_xlim': (-5, 5),
            'VIS_ylim': (0, 10),
            'VIS_zlim': (0, 3)
        },
        'RADAR_CFG_LIST': [{'name': n} for n in args.radars],
        'TRACK_FUSION_CFG': {
            'distance_threshold': 0.5
        },
        'INDUSTRIAL_VIS_CFG': {
            'enable': True,
            'output_protocol': 'udp',
            'ip_address': '127.0.0.1',
            'port': 5000
        }
    }

    # Instantiate visualizer object (not running yet)
    vis = FuseDualRadar(run_flag, radar_rd_queue_list, manager.Queue(), shared_dict, **kwargs_CFG)

    # Run visualizer in separate process so it can consume the manager queues
    def vis_proc():
        try:
            vis.run()
        except KeyboardInterrupt:
            print("Visualizer interrupted")
            run_flag.value = False

    p = Process(target=vis_proc, daemon=True)
    p.start()

    # Create mapping radar_name->queue for feeder
    queues_by_name = {args.radars[i]: queues[i] for i in range(len(args.radars))}

    try:
        if args.csv:
            frames = read_csv_to_frames(args.csv)
            # Group frames into cycles: we want to send frames from all radars per timestep if they exist.
            # We'll send one radar frame at a time but keep them in buffer.
            # For simplicity send frames sequentially with small delay.
            for f in frames:
                queues_by_name[f['radar_name']].put(f)
                time.sleep(0.01)
        else:
            if not args.synthetic:
                print("No CSV provided; defaulting to synthetic generator.")
            gen = synthetic_generator(n_frames=args.frames, n_objects=2, radar_names=args.radars)
            feeder_from_frames(gen, queues_by_name, delay=0.0)

        # Let the sim run a bit (or press Ctrl+C)
        print("Simulation feeding complete. Press Ctrl+C to stop.")
        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("Stopping simulation...")
    finally:
        run_flag.value = False
        time.sleep(0.2)
        if p.is_alive():
            p.terminate()
            p.join(timeout=1.0)
        print("Exited.")


if __name__ == '__main__':
    main()
