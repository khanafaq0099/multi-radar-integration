"""
Designed for data visualization, abbr. VIS
"""

import math
import queue
import time
from datetime import datetime
from multiprocessing import Manager

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.ticker import LinearLocator


RP_colormap = ['C5', 'C7', 'C8']  # the colormap for radar raw points
SNR_colormap = ['lavender', 'thistle', 'violet', 'darkorchid', 'indigo']  # the colormap for radar energy strength
OS_colormap = ['grey', 'green', 'gold', 'red']  # the colormap for object status


class Visualizer:
    def __init__(self, run_flag, vis_rd_queue, shared_param_dict, **kwargs_CFG):
        print("------------------------------Initializing Visualizer...")
        """
        get shared values and queues
        """
        self.run_flag = run_flag
        # fused track data in the queue
        self.vis_rd_queue = vis_rd_queue
        # shared params
        try:
            self.save_queue = shared_param_dict['save_queue']
        except:
            self.save_queue = Manager().Queue(maxsize=0)
        self.mansave_flag = shared_param_dict['mansave_flag']
        self.autosave_flag = shared_param_dict['autosave_flag']
        self.status = shared_param_dict['proc_status_dict']
        self.status['Module_VIS'] = True
        """
        pass config static parameters
        """
        """ module own config """
        VIS_CFG = kwargs_CFG['VISUALIZER_CFG']
        self.dimension = VIS_CFG['dimension']
        self.VIS_xlim = VIS_CFG['VIS_xlim']
        self.VIS_ylim = VIS_CFG['VIS_ylim']
        self.VIS_zlim = VIS_CFG['VIS_zlim']
        self.text_list = []
        self.auto_inactive_skip_frame = VIS_CFG['auto_inactive_skip_frame']

        """ other configs """
        self.MANSAVE_ENABLE = kwargs_CFG['MANSAVE_ENABLE']
        self.AUTOSAVE_ENABLE = kwargs_CFG['AUTOSAVE_ENABLE']
        self.RDR_CFG_LIST = kwargs_CFG['RADAR_CFG_LIST']

        # setup for matplotlib plot
        matplotlib.use('TkAgg')  # set matplotlib backend
        plt.rcParams['toolbar'] = 'None'  # disable the toolbar
        # create a figure
        self.fig = plt.figure()
        # adjust figure position
        mngr = plt.get_current_fig_manager()
        mngr.window.wm_geometry('+30+30')
        # draws a completely frameless window
        win = plt.gcf().canvas.manager.window
        win.overrideredirect(1)
        # interactive mode on, no need plt.show()
        plt.ion()

        self._log('Start...')

    # module entrance
    def run(self):
        if self.dimension == '2D':
            # create a plot
            ax1 = self.fig.add_subplot(111)

            while self.run_flag.value:
                # clear and reset
                plt.cla()
                ax1.set_xlim(self.VIS_xlim[0], self.VIS_xlim[1])
                ax1.set_ylim(self.VIS_ylim[0], self.VIS_ylim[1])
                ax1.xaxis.set_major_locator(LinearLocator(5))  # set axis scale
                ax1.yaxis.set_major_locator(LinearLocator(5))
                ax1.set_xlabel('x')
                ax1.set_ylabel('y')
                ax1.set_title('Radar')
                # update the canvas
                self._update_canvas(ax1)

        elif self.dimension == '3D':
            # create a plot
            ax1 = self.fig.add_subplot(111, projection='3d')

            spin = 0
            while self.run_flag.value:
                # clear and reset
                plt.cla()
                ax1.set_xlim(self.VIS_xlim[0], self.VIS_xlim[1])
                ax1.set_ylim(self.VIS_ylim[0], self.VIS_ylim[1])
                ax1.set_zlim(self.VIS_zlim[0], self.VIS_zlim[1])
                ax1.xaxis.set_major_locator(LinearLocator(3))  # set axis scale
                ax1.yaxis.set_major_locator(LinearLocator(3))
                ax1.zaxis.set_major_locator(LinearLocator(3))
                ax1.set_xlabel('x')
                ax1.set_ylabel('y')
                ax1.set_zlabel('z')
                ax1.set_title('Radar')
                # spin += 0.04
                ax1.view_init(ax1.elev - 0.5 * math.sin(spin), ax1.azim - 0.3 * math.sin(1.5 * spin))  # spin the view angle
                # update the canvas
                self._update_canvas(ax1)
        else:
            while self.run_flag.value:
                for q in self.radar_rd_queue_list:
                    _ = q.get(block=True, timeout=5)
    
    

    #     # Draw fused tracks
    #     if fused_tracks and len(fused_tracks) > 0:
    #         for track in fused_tracks:
    #             x, y, z = track['posX'], track['posY'], track['posZ']
    #             ax1.scatter(x, y, z, c='blue', marker='o', s=60)
    #             ax1.text(x, y, z + 0.1, f"T{track['global_tid']}", color='black', fontsize=8)
    #     else:
    #         self._log("No valid tracks to display.")
            
    #     plt.draw()
    #     plt.pause(0.001)
    def _update_canvas(self, ax1):
        """
        Efficient real-time 3D visualization of fused tracks (TLV 1010 output)
        """

        # Try to get fused data (non-blocking, short timeout for smooth refresh)
        try:
            fused_tracks = self.vis_rd_queue.get(timeout=0.05)
        except queue.Empty:
            fused_tracks = []

        # If first time setup — initialize scatter and radar markers
        if not hasattr(self, 'initialized'):
            ax1.set_xlim(self.VIS_xlim[0], self.VIS_xlim[1])
            ax1.set_ylim(self.VIS_ylim[0], self.VIS_ylim[1])
            ax1.set_zlim(self.VIS_zlim[0], self.VIS_zlim[1])
            ax1.set_xlabel('X (m)')
            ax1.set_ylabel('Y (m)')
            ax1.set_zlabel('Z (m)')
            ax1.set_title('3D People Tracking - Fused Tracks')

            # Plot radar positions once
            for RDR_CFG in self.RDR_CFG_LIST:
                ax1.scatter(
                    [RDR_CFG['pos_offset'][0]],
                    [RDR_CFG['pos_offset'][1]],
                    [RDR_CFG['pos_offset'][2]],
                    marker='^', color='darkred', s=80
                )

            # Empty scatter plot for fused tracks
            self.scat = ax1.scatter([], [], [], c='blue', marker='o', s=60)
            self.text_elems = []  # store text labels
            self.initialized = True

            plt.draw()
            plt.pause(0.001)
            return

        # If we have fused tracks, update scatter positions
        if fused_tracks and len(fused_tracks) > 0:
            xs = [t['posX'] for t in fused_tracks]
            ys = [t['posY'] for t in fused_tracks]
            zs = [t['posZ'] for t in fused_tracks]

            # Update scatter points efficiently
            self.scat._offsets3d = (xs, ys, zs, c='blue', marker='o')

            # Clear old labels and draw new ones
            for txt in self.text_list:
                try:
                    txt.remove()
                except Exception:
                    pass
            self.text_list.clear()

            self.text_elems = []
            for i, track in enumerate(fused_tracks):
                self.text_elems.append(
                    ax1.text(xs[i], ys[i], zs[i] + 0.1,
                            f"T{track['global_tid']}", color='black', fontsize=8)
                )
        else:
            # No data received recently
            pass

        # Refresh visualization (non-blocking)
        plt.draw()
        plt.pause(0.001)


    def _plot(self, ax, x, y, z, fmt='', **kwargs):
        """
        :param ax: the current canvas
        :param x: data in x-axis
        :param y: data in y-axis
        :param z: data in z-axis
        :param fmt: plot and plot3D fmt
        :param kwargs: plot and plot3D marker, linestyle, color
        :return: None
        """
        if len(fmt) > 0:  # if fmt is using
            if self.dimension == '2D':
                ax.plot(x, y, fmt)
            elif self.dimension == '3D':
                ax.plot3D(x, y, z, fmt)
        else:  # if para is using
            for i in ['marker', 'linestyle', 'color']:
                if not (i in kwargs):
                    kwargs[i] = 'None'
            if self.dimension == '2D':
                ax.plot(x, y, marker=kwargs['marker'], linestyle=kwargs['linestyle'], color=kwargs['color'])
            elif self.dimension == '3D':
                ax.plot3D(x, y, z, marker=kwargs['marker'], linestyle=kwargs['linestyle'], color=kwargs['color'])

    def _detect_key_press(self, timeout):  # error caused if the key is pressed at very beginning (first loop)
        keyPressed = plt.waitforbuttonpress(timeout=timeout)  # detect whether key is pressed or not
        plt.gcf().canvas.mpl_connect('key_press_event', self._press)  # detect which key is pressed
        if keyPressed:
            if self.the_key == 'escape':
                self.run_flag.value = False
            # manual save trigger
            if self.MANSAVE_ENABLE:
                if self.the_key == '+':
                    # activate flag
                    self.mansave_flag.value = 'image'
                elif self.the_key == '0':
                    # activate flag
                    self.mansave_flag.value = 'video'

    def _press(self, event):
        self.the_key = event.key

    def _log(self, txt):  # print with device name
        print(f'[{self.__class__.__name__}]\t{txt}')

    def __del__(self):
        plt.close(self.fig)
        self._log(f"Closed. Timestamp: {datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}")
        self.status['Module_VIS'] = False
        self.run_flag.value = False
