# -*- coding: utf-8 -*-
"""
Created on Mon May 5 16:33:32 2025

@authors: Andrea Bassi, Yoginder Singh, Politecnico di Milano
"""
from ScopeFoundry import BaseMicroscopeApp

class camera_app(BaseMicroscopeApp):
    

    name = 'camera_app'
    
    def setup(self):
        
        #Add hardware components
        print("Adding Hardware Components")
        from camera_hw import IdsHW
        self.add_hardware(IdsHW(self))
        
        # Add measurement components
        print("Create Measurement objects")
        from camera_measure_with_object_recognition import IdsMeasure
        self.add_measurement(IdsMeasure(self))


if __name__ == '__main__':
    import sys
    import os
    
    app = camera_app(sys.argv)
    
    path = os.path.dirname(os.path.realpath(__file__))
    new_path = os.path.join(path, 'Settings', 'Settings.ini')
    print(new_path)

    #`app.settings_load_ini(new_path)
    # connect all the hardwares
    #for hc_name, hc in app.hardware.items():
    #    hc.settings['connected'] = True


    sys.exit(app.exec_())