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
        
        self.settings.New('save_h5', dtype=bool, initial=False)         
        self.settings.New('refresh_period', dtype = float, unit ='s', spinbox_decimals = 3, initial = 0.08, vmin = 0) 

        self.frame_num = self.settings.New(name='frame_num',initial= 10, spinbox_step = 1,
                                           dtype=int, ro=False)       
        
        self.settings.New('xsampling', dtype=float, unit='um', initial=0.0586, spinbox_decimals = 3) 
        self.settings.New('ysampling', dtype=float, unit='um', initial=0.0586, spinbox_decimals = 3)
        self.settings.New('zsampling', dtype=float, unit='um', initial=1.0)
        
        self.auto_range = self.settings.New('auto_range', dtype=bool, initial=True)
        self.settings.New('auto_levels', dtype=bool, initial=True)
        self.settings.New('level_min', dtype=int, initial=60)
        self.settings.New('level_max', dtype=int, initial=4000)
        
        
        self.image_gen = self.app.hardware['IDS'] 
        
    def setup_figure(self):
        """
        Runs once during App initialization, after setup()
        This is the place to make all graphical interface initializations,
        build plots, etc.
        """
        
        # connect ui widgets to measurement/hardware settings or functions
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        self.settings.save_h5.connect_to_widget(self.ui.save_h5_checkBox)
        self.settings.auto_levels.connect_to_widget(self.ui.autoLevels_checkbox)
        self.settings.auto_range.connect_to_widget(self.ui.autoRange_checkbox)
        self.settings.level_min.connect_to_widget(self.ui.min_doubleSpinBox) 
        self.settings.level_max.connect_to_widget(self.ui.max_doubleSpinBox) 
                
        # Set up pyqtgraph graph_layout in the UI
        self.imv = pg.ImageView()
        self.ui.imageLayout.addWidget(self.imv)
        colors = [(0, 0, 0),
                  (45, 5, 61),
                  (84, 42, 55),
                  (150, 87, 60),
                  (208, 171, 141),
                  (255, 255, 255)
                  ]
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)
        self.imv.setColorMap(cmap)
        
    def update_display(self):
        """
        Displays (plots) the numpy array self.buffer. 
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
        self.display_update_period = self.settings['refresh_period'] 
       
        length = self.frame_num.val
        
        self.settings['progress'] = (self.frame_index +1) * 100/length
        
        
        
        if hasattr(self, 'img'):
            self.imv.setImage(self.img.T,
                                autoLevels = self.settings['auto_levels'],
                                autoRange = self.auto_range.val,
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
        first_frame_acquired = False
        frame_num  = self.frame_num.val
        self.frame_index = 0
        #nm = self.image_gen.camera.remote_nodemap
        self.image_gen.camera.remote_nodemap.FindNode("AcquisitionMode").SetCurrentEntry("Continuous")
        #nm.FindNode("AcquisitionMode").SetCurrentEntry("MultiFrame")
        #nm.FindNode("AcquisitionFrameCount").SetValue(int(frame_num)) 
        self.image_gen.camera.start_acquisition(int(frame_num))
        t = time.perf_counter()

        for frame_idx, img in enumerate(self.image_gen.camera.get_multiple_frames(frame_num)):
            self.img = img
            
            self.frame_index = frame_idx
            # dt = time.perf_counter() - t
            # print(f"Frame {frame_idx}: shape={img.shape}, Δt={dt:.4f}s")
            # t = time.perf_counter()

            if self.interrupt_measurement_called:
                break
            
            if not first_frame_acquired:
                self.create_h5_file()
                first_frame_acquired = True
                    
            self.image_h5[frame_idx,:,:] = img
            self.h5file.flush()
        
        self.image_gen.camera.stop_acquisition()
        self.h5file.close()
        self.settings['save_h5'] = False
    
    def run(self):
        """
        Runs when measurement is started. Runs in a separate thread from GUI.
        It should not update the graphical interface directly, and should only
        focus on data acquisition.
        """
        self.image_gen.read_from_hardware()
        
        try:
            self.frame_index = -1
            self.image_gen.camera.remote_nodemap.FindNode("AcquisitionMode").SetCurrentEntry("Continuous")
            self.image_gen.settings['exposure_mode'] = 'Timed'
            self.image_gen.camera.start_acquisition() 
            
            while not self.interrupt_measurement_called:
                     
                self.img = self.image_gen.camera.get_last_frame()
                
                if self.interrupt_measurement_called:
                    self.image_gen.camera.stop_acquisition() 
                    break
                
                if self.settings['save_h5']:
                    # measure is triggered by save_h5 button
                    self.image_gen.camera.stop_acquisition() 
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
                   

    