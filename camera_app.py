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
        from camera_measure import IdsMeasure
        self.add_measurement(IdsMeasure(self))

        #self.ui.show()
        #self.ui.activateWindow()


if __name__ == '__main__':
    import sys
    
    app = camera_app(sys.argv)
    sys.exit(app.exec_())