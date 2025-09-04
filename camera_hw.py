# -*- coding: utf-8 -*-
"""
Created on Mon May 5 16:33:32 2025

@authors: Andrea Bassi, Yoginder Singh, Politecnico di Milano
"""
from ScopeFoundry import HardwareComponent
from ids import Camera

class IdsHW(HardwareComponent):
    name = 'IDS'
    
    def setup(self):
        # create Settings (aka logged quantities)
        # self.infos = self.add_logged_quantity('name', dtype=str)     
        self.infos = self.settings.New(name='name', dtype=str)
        self.temperature = self.settings.New(name='temperature', dtype=float, ro=True, unit=chr(176)+'C' )
        self.image_width = self.settings.New(name='image_width', dtype=int, ro=True,unit='px')
        self.image_height = self.settings.New(name='image_height', dtype=int, ro=True,unit='px')
        self.bit_depth = self.settings.New(name='bit_depth', dtype=int,
                                                  choices=[8, 10,12], initial = 10, ro=False)
        self.gain = self.settings.New(name='gain', initial=1., dtype=float,
                                      vmax = 1000., vmin = 1., spinbox_step = 1.,
                                      ro=False)
        self.frame_rate = self.settings.New(name='frame_rate', initial= 9,
                                            vmax = 1000., vmin = 0.01, spinbox_step = 0.1,
                                            unit = 'fps',dtype=float, ro=False, reread_from_hardware_after_write=True)
        self.exposure_time = self.settings.New(name='exposure_time', initial=100, vmax =5000.,
                                               vmin = 0.01, spinbox_step = 0.1,dtype=float, ro=False, unit='ms',reread_from_hardware_after_write=True)
        self.exposure_mode = self.settings.New(name='exposure_mode', dtype=str,
                                                  choices=['Timed', 'TriggerControlled'], initial = 'Timed', ro=False)
        
    def connect(self):
        # create an instance of the Device
        self.camera = Camera()      
        
        # connect settings to Device methods
        self.image_width.hardware_read_func = self.camera.get_width
        self.image_height.hardware_read_func = self.camera.get_height
        self.bit_depth.hardware_set_func = self.camera.set_bit_depth
        #self.infos.hardware_read_func = self.camera.get_idname
        self.exposure_time.hardware_read_func = self.camera.get_exposure_ms
        self.exposure_time.hardware_set_func = self.camera.set_exposure_ms
        self.frame_rate.hardware_read_func = self.camera.get_frame_rate
        self.frame_rate.hardware_set_func = self.camera.set_frame_rate
        #self.acquisition_mode.hardware_set_func = self.camera.set_acquisitionmode
        #self.frame_num.hardware_set_func = self.camera.set_framenum
        self.gain.hardware_set_func = self.camera.set_gain
        self.read_from_hardware()
        
    def disconnect(self):
        if hasattr(self, 'camera'):
            self.camera.close() 
            del self.camera
            
        for lq in self.settings.as_list():
            lq.hardware_read_func = None
            lq.hardware_set_func = None

