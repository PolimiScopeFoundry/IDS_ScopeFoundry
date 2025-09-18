# -*- coding: utf-8 -*-
"""
Created on Mon May 5 16:33:32 2025

@authors: Andrea Bassi, Yoginder Singh, Politecnico di Milano
"""
from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from ScopeFoundry import h5_io
import pyqtgraph as pg
import numpy as np
import os, time
from pyqtgraph.Qt import QtWidgets
from image_data import ImageManager

class IdsMeasure(Measurement):
    
    # this is the name of the measurement that ScopeFoundry uses 
    # when displaying your measurement and saving data related to it    
    name = "ids_measure_objects_recognition"
    
    def setup(self):
        """
        Runs once during App initialization.
        This is the place to load a user interface file,
        define settings, and set up data structures. 
        """
        
        # Define ui file to be used as a graphical interface
        # This file can be edited graphically with Qt Creator
        # sibling_path function allows python to find a file in the same folder
        # as this python module
        self.ui_filename = sibling_path(__file__, "camera_with_object_recognition.ui")
        
        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        # Measurement Specific Settings
        # This setting allows the option to save data to an h5 data file during a run
        # All settings are automatically added to the Microscope user interface

        self.settings.New('saving_type', dtype=str, initial='None', choices=['None', 'Roi', 'Stack'])
        self.settings.New('roi_size', dtype=int, initial=200, vmin=2)
        self.settings.New('min_object_area', dtype=int, initial=250, vmin=1)
        self.settings.New('max_object_area', dtype=int, initial=10000, vmin=1)
        self.settings.New('selected_channel', dtype=int, initial=0, vmin=0, vmax=0) #TODO setv max to the max channel number
        
        
        self.settings.New('captured_objects', dtype=int, initial=0, ro=True)
        self.settings.New('objects_in_frame', dtype=int, initial=0, ro=True)
        
        self.settings.New('frame_num', dtype=int, initial=20, vmin=1)
        self.settings.New('channel_num', dtype=int, initial=1, vmin=1)
        
        self.settings.New('xsampling', dtype=float, unit='um', initial=0.5)
        self.settings.New('ysampling', dtype=float, unit='um', initial=0.5)
        self.settings.New('zsampling', dtype=float, unit='um', initial=3.0)
    
        self.settings.New('auto_range', dtype=bool, initial=True)
        self.settings.New('auto_levels', dtype=bool, initial=True)
        self.settings.New('level_min', dtype=int, initial=60)
        self.settings.New('level_max', dtype=int, initial=4000)

        self.settings.New('detect', dtype=bool, initial=False)
        self.settings.New('sampling_period', dtype=float, unit='s', initial=0.1)
        self.settings.New('zoom', dtype=int, initial=50, vmin=25, vmax=100)
        self.settings.New('rotate', dtype=bool, initial=True)
        
        # Convenient reference to the hardware used in the measurement
        self.camera = self.app.hardware['IDS'] 


    def setup_figure(self):
        """
        Runs once during App initialization, after setup()
        This is the place to make all graphical interface initializations,
        build plots, etc.
        """
        
        # connect ui widgets to measurement/hardware settings or functions
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)

        self.settings.detect.connect_to_widget(self.ui.detect_checkBox)
        self.settings.saving_type.connect_to_widget(self.ui.save_comboBox)

        self.settings.captured_objects.connect_to_widget(self.ui.num_objects_SpinBox)
        self.settings.objects_in_frame.connect_to_widget(self.ui.objects_in_frame_SpinBox)

        self.settings.auto_levels.connect_to_widget(self.ui.autoLevels_checkbox)
        self.settings.auto_range.connect_to_widget(self.ui.autoRange_checkbox)
        self.settings.level_min.connect_to_widget(self.ui.min_doubleSpinBox) 
        self.settings.level_max.connect_to_widget(self.ui.max_doubleSpinBox)
        self.settings.zoom.connect_to_widget(self.ui.zoomSlider)
        self.settings.rotate.connect_to_widget(self.ui.rotate_checkBox)
                
        # Set up pyqtgraph graph_layout in the UI
        self.imv = pg.ImageView()
        self.imv.ui.histogram.hide()
        self.imv.ui.roiBtn.hide()
        self.imv.ui.menuBtn.hide()
        self.ui.image_layout.addWidget(self.imv)
        colors = [(0, 0, 0),
                  (45, 5, 61),
                  (84, 42, 55),
                  (150, 87, 60),
                  (208, 171, 141),
                  (255, 255, 255)
                  ]
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)
        self.imv.setColorMap(cmap)
        self.screen_width = self.ui.screen().size().width() # Get screen width to be used for zooming


    def update_display(self):
        """
        Displays (plots) the numpy array self.buffer. 
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
        self.display_update_period = self.settings['sampling_period']

        # Remove previous overlays
        for item in self.imv.getView().allChildItems():
            if isinstance(item, (pg.PlotCurveItem, QtWidgets.QGraphicsRectItem)):
                self.imv.getView().removeItem(item)

        # Plot countours and rectangles around detected objects
        roisize = self.settings['roi_size']
        
        #time0 = time.time()
        ch = self.settings.selected_channel.val
        im = self.im.copy()
        img = im.image[ch,...]

        if self.settings.saving_type.val == 'None':
            self.screen_width = self.ui.screen().size().width()
            width = int(self.screen_width*self.settings['zoom']/100)
            self.ui.setFixedWidth(width)

        for indx, cnt in enumerate(im.contours):
            cnt = cnt.squeeze()
            if cnt.ndim == 2 and len(cnt) > 1:
                if self.settings['rotate']: 
                    curve = pg.PlotCurveItem(cnt[:, 0], cnt[:, 1], pen=pg.mkPen('g', width=0.5))
                else:
                    curve = pg.PlotCurveItem(cnt[:, 1], cnt[:, 0], pen=pg.mkPen('g', width=0.5))
                
                self.imv.getView().addItem(curve)
            
            x = int(im.cx[indx] - roisize//2)
            y = int(im.cy[indx] - roisize//2)
            if self.settings['rotate']:   
                rect = QtWidgets.QGraphicsRectItem(x, y, roisize, roisize)
            else:
                rect = QtWidgets.QGraphicsRectItem(y, x, roisize, roisize)
            rect.setPen(pg.mkPen(color='r', width=1))
            self.imv.getView().addItem(rect)


        if self.settings['rotate']:   
            img=img.T

        self.imv.setImage(img,
                        autoLevels = self.settings['auto_levels'],
                        autoRange = self.settings['auto_range'],
                        levelMode = 'mono'
                        )
            
        if self.settings['auto_levels']:
            lmin,lmax = self.imv.getHistogramWidget().getLevels()
            self.settings['level_min'] = lmin
            self.settings['level_max'] = lmax
        else:
            self.imv.setLevels( min= self.settings['level_min'],
                                max= self.settings['level_max'])


        if self.settings['saving_type'] == 'Stack' and hasattr(self, 'frame_index') and hasattr(self, 'channel_index'):
            z_idx = self.frame_index
            c_idx = self.channel_index
            frames=self.settings['frame_num']
            channels=self.settings['channel_num']
            progress = (c_idx + z_idx * (channels + 1)) * 100 / ((frames + 1) * (channels + 1) - 1)
            self.settings['progress'] = progress # Set progress bar percentage complete


    def pre_run(self):
        
        
        # Acquire initial image (1 for each channel) to set up the Image Manager
        self.camera.camera_device.remote_nodemap.FindNode("AcquisitionMode").SetCurrentEntry("Continuous") # Ids camera specific function
        self.camera.camera_device.start_acquisition()    
        
        self.channel_index = 0 
        self.first_run = True # flag for initializing h5 roi file
        while self.channel_index < self.settings.channel_num.val:
                       
            img = self.camera.camera_device.get_frame()
               
            if self.channel_index == 0:
                self.im = ImageManager(
                        img.shape[1], img.shape[0],
                        self.settings.roi_size.val,
                        Nchannels=self.settings.channel_num.val,
                        dtype=img.dtype
                        )
            self.im.image[self.channel_index,...] = img
            self.channel_index +=1


    def run(self):

        while not self.interrupt_measurement_called:
            
            self.channel_index = 0
            while self.channel_index < self.settings.channel_num.val:
                
                img = self.camera.camera_device.get_frame()
                
                self.im.image[self.channel_index,...] = img
                self.channel_index +=1   
            
            if self.settings['detect']:
                self.detect_objects()
            else:
                self.settings['objects_in_frame'] = 0
                self.im.clear_countours()      

            if self.settings['saving_type'] == 'Roi':
                if self.first_run:
                    _ = self.init_h5()
                    self.time_index = 0 # time index for h5 roi file
                    self.first_run = False
                self.save_roi()
            
            if self.settings['saving_type'] == 'Stack':
                self.settings['objects_in_frame'] = 0
                self.camera.camera_device.stop_acquisition()
                self.save_stack()
                break

            if self.interrupt_measurement_called:
                break

        self.camera.camera_device.stop_acquisition()  

    
    def save_roi(self):
        im = self.im
        cnum = self.settings['channel_num']
        znum = 1 # TODO: self.settings['frame_num'] # change to znum when z-stacks are implemented
        
        roisize = self.settings['roi_size']
        
        for roi_idx in range(len(im.cx)):
            for ch_idx in range(cnum):
                h5_roi_dataset = self.prepare_h5_dataset(self.time_index,
                                channels_index=ch_idx,
                                z_number=znum,
                                imshape=[roisize,roisize],
                                dtype=im.image.dtype,
                                name='roi',
                                )
                roi = im.extract_rois(ch_idx,im.cx,im.cy)
                h5_roi_dataset[0,:,:] = roi[roi_idx]
                self.time_index += 1
            self.settings['captured_objects'] += 1
            self.h5file.flush() 

            if self.interrupt_measurement_called or self.time_index >= 100:
                self.close_h5()
                self.settings['saving_type'] = 'None'
                self.first_run = True
                break

    def detect_objects(self):
        #time0 = time.time()
        self.im.find_object(self.settings.selected_channel.val,
                            self.settings.min_object_area.val, self.settings.max_object_area.val,
                            bitdepth=self.camera.camera_device.get_bit_depth())
        self.settings['objects_in_frame'] = len(self.im.contours)
        #print(f'Objects {self.settings['objects_in_frame']} acquired in {time.time()-time0:.3f} s')
            

    def save_stack(self):

        cnum=self.settings['channel_num']
        znum=self.settings['frame_num']
        
        images_h5 = self.init_h5()
        
        self.append_h5_dataset(h5_dataset_list=images_h5,
                                time_index=0,
                                channels_number=cnum,
                                z_number=znum,
                                imshape=self.im.image.shape[1:],
                                dtype=self.im.image.dtype,
                                name='stack',
                                )

        self.camera.camera_device.start_acquisition() 
        self.frame_index = 0
        while self.frame_index < self.settings.frame_num.val:
            self.channel_index = 0 
            while self.channel_index < self.settings.channel_num.val:
                
                img = self.camera.camera_device.get_frame() 
                
                images_h5[self.channel_index][self.frame_index,:,:] = img
                self.h5file.flush() # introduces a slight time delay but assures that images are stored continuosly 
                
                self.channel_index +=1
            if self.interrupt_measurement_called:
                    self.camera.camera_device.stop_acquisition()
                    break
            self.frame_index +=1  

        self.close_h5()
        self.settings['saving_type'] = 'None'


    def init_h5(self):

        if not os.path.isdir(self.app.settings['save_dir']):
            os.makedirs(self.app.settings['save_dir'])
        self.h5file = h5_io.h5_base_file(app=self.app, measurement=self)
        self.h5_group = h5_io.h5_create_measurement_group(measurement=self, h5group=self.h5file)
        h5_dataset_list = [] # image_h5 is a of h5 datasets
        return h5_dataset_list
    

    def append_h5_dataset(self, h5_dataset_list,
                        time_index=0,   
                        channels_number=2,
                        z_number=10, imshape=[512,256],
                        dtype='uint16', name='image'):
        
        shape=[z_number, imshape[0], imshape[1]]
        for channel_idx in range(channels_number):
            dataset = self.h5_group.create_dataset(name = f't{time_index}/c{channel_idx}/{name}', 
                                                        shape = shape,
                                                        dtype = dtype)  
            dataset.attrs['element_size_um'] = [self.settings['zsampling'], self.settings['ysampling'], self.settings['xsampling']]
            h5_dataset_list.append(dataset)
    
    def prepare_h5_dataset(self,
                        time_index=0,   
                        channels_index=0,
                        z_number=10, imshape=[512,256],
                        dtype='uint16', name='image'):
        
        shape=[z_number, imshape[0], imshape[1]]
        h5_dataset = self.h5_group.create_dataset(name = f't{time_index}/c{channels_index}/{name}', 
                                                        shape = shape,
                                                        dtype = dtype)
        h5_dataset.attrs['element_size_um'] = [self.settings['zsampling'], self.settings['ysampling'], self.settings['xsampling']]
              
        return h5_dataset    
    
    def remove_h5_dataset(self, h5_dataset_list, dataset_idx=0):
        h5_dataset = h5_dataset_list.pop(dataset_idx)
        return h5_dataset
    
    def close_h5(self):
        self.h5file.close()
        if hasattr(self,'h5file'):  
            delattr(self, 'h5file')
        if hasattr(self,'h5_group'):    
            delattr(self, 'h5_group')


