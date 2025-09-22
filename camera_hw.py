# -*- coding: utf-8 -*-
"""
Created on Mon May 5 16:33:32 2025

@authors: Andrea Bassi, Yoginder Singh, Politecnico di Milano
"""
from ScopeFoundry import HardwareComponent
from ids_library import Camera, BitDepthChoices

class IdsHW(HardwareComponent):
    name = 'IDS'
    
    def setup(self):
        # create Settings (aka logged quantities)   
        self.model = self.settings.New(name='model', dtype=str)
        self.temperature = self.settings.New(name='temperature', dtype=float, ro=True, unit=chr(176)+'C' )
        self.image_width = self.settings.New(name='image_width', dtype=int, ro=True,unit='px')
        self.image_height = self.settings.New(name='image_height', dtype=int, ro=True,unit='px')
        self.bit_depth = self.settings.New(name='bit_depth', dtype=int,
                                                choices=list(BitDepthChoices.keys()),
                                                initial = 16, ro=False,
                                                reread_from_hardware_after_write=True)
        self.gain = self.settings.New(name='gain', initial=1., dtype=float,
                                      vmax = 1000., vmin = 1., spinbox_step = 1.,
                                      ro=False, reread_from_hardware_after_write=True)
        self.frame_rate = self.settings.New(name='frame_rate', initial= 9,
                                            vmax = 1000., vmin = 0.01, spinbox_step = 0.1,
                                            unit = 'fps',dtype=float, ro=False, reread_from_hardware_after_write=True)
        self.exposure_time = self.settings.New(name='exposure_time', initial=100, vmax =5000.,
                                               vmin = 0.01, spinbox_step = 0.1,dtype=float, ro=False, unit='ms',
                                               reread_from_hardware_after_write=True)
        self.acquisition_mode = self.settings.New(name='acquisition_mode', dtype=str,
                                                choices=['Continuous', 'MultiFrame', 'SingleFrame'], 
                                                initial = 'Continuous', ro=False)

        self.exposure_mode = self.settings.New(name='exposure_mode', dtype=str,
                                                choices=['Timed', 'TriggerControlled'], 
                                                initial = 'Timed', ro=False)
        
        self.stream_mode = self.settings.New(name='stream_mode', dtype= str,
                                                choices=['NewestOnly', 'OldestFirst',
                                                         'OldestFirstSingleBuffer','OldestFirstDependOnCameraFIFO'], 
                                                initial = 'OldestFirst', ro=False)
                                             
        

    
    def connect(self):
        # create an instance of the Device
        self.camera_device = Camera(debug=self.settings['debug_mode'])
        
        # connect settings to Device methods
        self.model.hardware_read_func = self.camera_device.get_model
        self.image_width.hardware_read_func = self.camera_device.get_width
        self.image_height.hardware_read_func = self.camera_device.get_height
        self.bit_depth.hardware_set_func = self.camera_device.set_bit_depth
        self.bit_depth.hardware_read_func = self.camera_device.get_bit_depth
        self.exposure_time.hardware_read_func = self.camera_device.get_exposure_ms
        self.exposure_time.hardware_set_func = self.camera_device.set_exposure_ms
        self.frame_rate.hardware_read_func = self.camera_device.get_frame_rate
        self.frame_rate.hardware_set_func = self.camera_device.set_frame_rate
        self.gain.hardware_set_func = self.camera_device.set_gain
        self.gain.hardware_read_func = self.camera_device.get_gain
        self.debug_mode.hardware_read_func = self.camera_device.get_debug_mode
        self.debug_mode.hardware_set_func = self.camera_device.set_debug_mode
        self.acquisition_mode.hardware_read_func = self.camera_device.get_acquisition_mode
        self.acquisition_mode.hardware_set_func = self.camera_device.set_acquisition_mode
        self.stream_mode.hardware_read_func = self.camera_device.get_stream_mode
        self.stream_mode.hardware_set_func = self.camera_device.set_stream_mode
        
        self.read_from_hardware()
        
    def disconnect(self):
        if hasattr(self, 'camera_device'):
            self.camera_device.close() 
            del self.camera_device
            
        for lq in self.settings.as_list():
            lq.hardware_read_func = None
            lq.hardware_set_func = None

