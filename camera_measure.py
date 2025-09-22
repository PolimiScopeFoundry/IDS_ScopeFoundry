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

class IdsMeasure(Measurement):
    
    name = "IDSmeasurement"
    
    def setup(self):
        """
        Runs once during App initialization.
        This is the place to load a user interface file,
        define settings, and set up data structures.
        """
        
        self.ui_filename = sibling_path(__file__, "camera.ui")
        self.ui = load_qt_ui_file(self.ui_filename) 
        
        self.settings.New('refresh_period', dtype = float, unit ='s', spinbox_decimals = 3, initial = 0.08, vmin = 0) 
        self.settings.New('saving_type', dtype=str, initial='None', choices=['None', 'Stack'])
        
        self.frame_num = self.settings.New(name='frame_num',initial= 10, spinbox_step = 1,
                                           dtype=int, ro=False)  
        
        self.settings.New('zoom', dtype=int, initial=50, vmin=25, vmax=100)
        self.settings.New('rotate', dtype=bool, initial=True)     
        
        self.settings.New('xsampling', dtype=float, unit='um', initial=0.0586, spinbox_decimals = 3) 
        self.settings.New('ysampling', dtype=float, unit='um', initial=0.0586, spinbox_decimals = 3)
        self.settings.New('zsampling', dtype=float, unit='um', initial=1.0)
        
        self.auto_range = self.settings.New('auto_range', dtype=bool, initial=True)
        self.settings.New('auto_levels', dtype=bool, initial=True)
        self.settings.New('level_min', dtype=int, initial=60)
        self.settings.New('level_max', dtype=int, initial=4000)
        
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
        self.settings.saving_type.connect_to_widget(self.ui.save_comboBox)
        self.settings.auto_levels.connect_to_widget(self.ui.autoLevels_checkbox)
        self.settings.auto_range.connect_to_widget(self.ui.autoRange_checkbox)
        self.settings.level_min.connect_to_widget(self.ui.min_doubleSpinBox) 
        self.settings.level_max.connect_to_widget(self.ui.max_doubleSpinBox)
        self.settings.zoom.connect_to_widget(self.ui.zoomSlider)
        self.settings.rotate.connect_to_widget(self.ui.rotate_checkBox) 
                
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
        self.display_update_period = self.settings['refresh_period'] 
       
        length = self.frame_num.val

        if self.settings.saving_type.val == 'None':
            self.screen_width = self.ui.screen().size().width()
            width = int(self.screen_width*self.settings['zoom']/100)
            self.ui.setFixedWidth(width)
        
        if self.settings['saving_type'] == 'Stack' and hasattr(self,'frame_index'):
            self.settings['progress'] = (self.frame_index +1) * 100/length
        
        if hasattr(self,'img'):

            img=self.img
            
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
                
    
    def measure(self):
        """
        Acquire frame_num frames and save them in h5 
        """

        frame_num  = self.frame_num.val
        self.camera.camera_device.set_acquisition_mode("MultiFrame")
        self.camera.camera_device.set_frame_num(frame_num)
        self.camera.camera_device.set_stream_mode("OldestFirst")

        self.frame_index = 0
        
        self.camera.camera_device.start_acquisition()

        self.create_h5_file()

        t = time.perf_counter()

        for frame_idx in range(frame_num):
        
            img = self.camera.camera_device.get_frame()

            self.img = img
            
            self.frame_index = frame_idx

            if self.interrupt_measurement_called:
                break
                    
            self.image_h5[frame_idx,:,:] = img
        
        self.h5file.flush()
        self.camera.camera_device.stop_acquisition()
        self.camera.camera_device.set_acquisition_mode("Continuous")
        self.h5file.close()
        self.settings['saving_type'] = 'None'

    
    def run(self):
        """
        Runs when measurement is started. Runs in a separate thread from GUI.
        It should not update the graphical interface directly, and should only
        focus on data acquisition.
        """
        self.camera.read_from_hardware()
        
        try:
            self.frame_index = -1
            self.camera.camera_device.set_acquisition_mode("Continuous")
            self.camera.camera_device.set_stream_mode("NewestOnly")
            self.camera.camera_device.start_acquisition() 
            
            while not self.interrupt_measurement_called:
                     
                self.img = self.camera.camera_device.get_frame()
                
                if self.interrupt_measurement_called:
                    self.camera.camera_device.stop_acquisition() 
                    break
                
                if self.settings['saving_type'] == 'Stack':
                    # measure is triggered by save_h5 button
                    self.camera.camera_device.stop_acquisition() 
                    self.measure()
                    break
        finally:
            pass
         
    def create_saving_directory(self):
        
        if not os.path.isdir(self.app.settings['save_dir']):
            os.makedirs(self.app.settings['save_dir'])
        
    
    def create_h5_file(self):                   
        self.create_saving_directory()
        # file name creation
        timestamp = time.strftime("%y%m%d_%H%M%S", time.localtime())
        sample = self.app.settings['sample']
        #sample_name = f'{timestamp}_{self.name}_{sample}.h5'
        if sample == '':
            sample_name = '_'.join([timestamp, self.name])
        else:
            sample_name = '_'.join([timestamp, self.name, sample])
        fname = os.path.join(self.app.settings['save_dir'], sample_name + '.h5')
        
        self.h5file = h5_io.h5_base_file(app=self.app, measurement=self, fname = fname)
        self.h5_group = h5_io.h5_create_measurement_group(measurement=self, h5group=self.h5file)
        
        img_size = self.img.shape
        dtype=self.img.dtype
        
        length = self.frame_num.val
        self.image_h5 = self.h5_group.create_dataset(name  = 't0/c0/image', 
                                                  shape = [length, img_size[0], img_size[1]],
                                                  dtype = dtype)
        self.image_h5.attrs['element_size_um'] =  [self.settings['zsampling'],self.settings['ysampling'],self.settings['xsampling']]
                   

    