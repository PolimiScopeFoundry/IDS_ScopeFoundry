from ids_peak import ids_peak
from ids_peak import ids_peak_ipl_extension
import warnings
import numpy

BitDepthChoices = {	8: "Mono8",
                    10: "Mono10",
                    12: "Mono12",
                    16: "Mono16"
                   }


class Camera:
    
    def __init__(self, cam_num=0, debug=False):
        ids_peak.Library.Initialize()
        device_manager = ids_peak.DeviceManager.Instance()
        device_manager.Update()
        self.device = device_manager.Devices()[cam_num].OpenDevice(ids_peak.DeviceAccessType_Control)
        # Nodemap for accessing GenICam nodes
        self.remote_nodemap = self.device.RemoteDevice().NodeMaps()[0]
        self.data_stream = self.device.DataStreams()[0].OpenDataStream()
        self.debug = debug
        self.trigger_task = None
        self._last_delay = 0.1
        self._current_frame_rate = 0

    def set_debug_mode(self, value):
        self.debug = value

    def get_debug_mode(self):
        return self.debug

    def get_model(self):
        return self.device.ModelName()

    def get_width(self):
        val = self.remote_nodemap.FindNode("Width").Value()
        if self.debug:
            print(f'Width {val} with maximum {self.get_size()[0]}')
        return val 

    def get_height(self):
        val = self.remote_nodemap.FindNode("Height").Value()
        if self.debug:
            print(f'Height {val} with maximum {self.get_size()[1]}')
        return val 

    def get_offsetx(self):
        val = self.remote_nodemap.FindNode("OffsetX").Value()
        if self.debug:
            print(f'OffsetX {val}')
        return val 
    
    def get_offsety(self):
        val = self.remote_nodemap.FindNode("OffsetY").Value()
        if self.debug:
            print(f'OffsetY {val}')
        return val 
    
    def set_width(self,w):
        x,y,_,h = self.get_active_region()
        self.set_active_region(x,y,w,h)
    
    def set_height(self,h):
        x,y,w,_ = self.get_active_region()
        self.set_active_region(x,y,w,h)

    def set_offsetx(self,x):
        _,y,w,h = self.get_active_region()
        self.set_active_region(x,y,w,h)

    def set_offsety(self,y):
        x,_,w,h = self.get_active_region()
        self.set_active_region(x,y,w,h)

    def get_size(self):
        """
        Gets the full size of the sensor"""
        return(self.remote_nodemap.FindNode("SensorWidth").Value(),self.remote_nodemap.FindNode("SensorHeight").Value())

    def set_node_value(self,name,value):
        val_min = self.remote_nodemap.FindNode(name).Minimum()
        val_max = self.remote_nodemap.FindNode(name).Maximum()
        if value<val_min:
            self.remote_nodemap.FindNode(name).SetValue(val_min)

        elif value>val_max:
            self.remote_nodemap.FindNode(name).SetValue(val_max)
        else:
            self.remote_nodemap.FindNode(name).SetValue(value)
        if self.debug:
            print(f'{name} set to {value} with min {val_min} and max {val_max}')

    def set_full_chip(self):
        self.remote_nodemap.FindNode("OffsetX").SetValue(0)
        self.remote_nodemap.FindNode("OffsetY").SetValue(0)
        self.remote_nodemap.FindNode("Width").SetValue(
            self.remote_nodemap.FindNode("Width").Maximum())
        self.remote_nodemap.FindNode("Height").SetValue(
            self.remote_nodemap.FindNode("Height").Maximum())

            

    def set_active_region(self,x,y,w,h):
        rn = self.remote_nodemap
        params = {"Width":w,
                  "Height":h,
                  "OffsetX": x,
                  "OffsetY": y}
        
        self.set_node_value("OffsetX",0)
        self.set_node_value("OffsetY",0)
        
        for key,val in params.items():

            self.set_node_value(key,val)


    def get_active_region(self):
        rn = self.remote_nodemap
        x = rn.FindNode("OffsetX").Value()
        y = rn.FindNode("OffsetY").Value()
        w = rn.FindNode("Width").Value()
        h = rn.FindNode("Height").Value()
        return x,y,w,h  


    def get_frame_rate(self):
        val = self.remote_nodemap.FindNode("AcquisitionFrameRate").Value()
        if self.debug: 
            max_val = self.remote_nodemap.FindNode("AcquisitionFrameRate").Maximum()
            print(f"Frame rate:{val}, with maximum available value: {max_val}")
        return val
    
    def set_frame_rate(self,framerate):
        max_rate = self.remote_nodemap.FindNode("AcquisitionFrameRate").Maximum()
        self.set_node_value("AcquisitionFrameRate", min(framerate, max_rate))
        if self.debug: self.get_frame_rate

    def get_exposure_ms(self):
        val = self.remote_nodemap.FindNode("ExposureTime").Value()/1000
        if self.debug: 
            min_val = self.remote_nodemap.FindNode("ExposureTime").Minimum()/1000
            print(f"ExposureTime: {val} ms, with minimum available value: {min_val} ms") 
        return val

    def set_exposure_ms(self,value):
        value=value*1000
        self.set_node_value("ExposureTime",value)
        max_exposure = self.remote_nodemap.FindNode("ExposureTime").Maximum()
        if value > max_exposure: 
            self.remote_nodemap.FindNode("AcquisitionFrameRate").SetValue(
                self.remote_nodemap.FindNode("AcquisitionFrameRate").Maximum())
        if self.debug: self.get_exposure_ms()

    def set_gain(self,value):
        self.set_node_value("Gain",value)


    def get_gain(self):
        val = self.remote_nodemap.FindNode("Gain").Value()
        if self.debug:
            max_val = self.remote_nodemap.FindNode("Gain").Maximum()
            print(f"Gain:{val}, with maximum gain available {max_val}")
        return val

    def get_available_bit_depths(self):
        nm=self.remote_nodemap
        allEntries = nm.FindNode("PixelFormat").Entries()
        availableEntries = []
        for entry in allEntries:
            if (entry.AccessStatus() != ids_peak.NodeAccessStatus_NotAvailable
                    and entry.AccessStatus() != ids_peak.NodeAccessStatus_NotImplemented):
                availableEntries.append(entry.SymbolicValue())
        return availableEntries
        
    def set_bit_depth(self,numeric_value):
        """ Sets the bit depth if available in the camera. If not available, sets the maximum available bit depth.

        Args:
            numeric_value (int): numeric value of the bit depth to be set. Possible values are in the BitDepthChoices dictionary    
        """
        nm = self.remote_nodemap
        if BitDepthChoices[numeric_value] in self.get_available_bit_depths():
            nm.FindNode("PixelFormat").SetCurrentEntry(BitDepthChoices[numeric_value])
        else:
            print("Selected bit depth not available. Setting to maximum available bit depth.")
            self.set_maximum_bit_depth()

    def set_maximum_bit_depth(self):
        """ Sets the maximum available bit depth
            and returns the numeric value of the set bit depth          
            Output: int: numeric value of the set bit depth. None if no bit depth is set"""
        choices_list = list(BitDepthChoices.keys())
        choices_list.sort(reverse=True)
        nm = self.remote_nodemap
        for numeric_value in choices_list:
            if BitDepthChoices[numeric_value] in self.get_available_bit_depths():
                nm.FindNode("PixelFormat").SetCurrentEntry(BitDepthChoices[numeric_value])
                return numeric_value # returns the numeric beatdepth and interrupts the cycle if an available bitdepth is set

    def get_bit_depth(self):
        nm = self.remote_nodemap
        symbolic_value = nm.FindNode("PixelFormat").CurrentEntry().SymbolicValue()
        for key,value in BitDepthChoices.items():
            if value==symbolic_value:
                return key

    def set_frame_num(self, nframes):
        nm = self.remote_nodemap
        nm.FindNode("AcquisitionMode").SetCurrentEntry("MultiFrame")
        nm.FindNode("AcquisitionFrameCount").SetValue(int(nframes))


    def set_acquisition_mode(self, mode="Continuous"):
        self.remote_nodemap.FindNode("AcquisitionMode").SetCurrentEntry(mode)
        

    def get_acquisition_mode(self):
        value=self.remote_nodemap.FindNode("AcquisitionMode").CurrentEntry().SymbolicValue()
        if self.debug:
            print(f"AcquisitionMode:{value}")
        return value


    def set_stream_mode(self,value):
        self.data_stream.NodeMaps()[0].FindNode("StreamBufferHandlingMode").SetCurrentEntry(value)


    def get_stream_mode(self):
        value = self.data_stream.NodeMaps()[0].FindNode("StreamBufferHandlingMode").CurrentEntry().SymbolicValue()
        if self.debug:
            print(f"StreamBufferHandlingMode:{value}")
        return value

    def read_node_safely(self, nm, node_name):
        try:
            node = nm.FindNode(node_name)
            status = node.AccessStatus()
            if status in (ids_peak.NodeAccessStatus_NotAvailable, ids_peak.NodeAccessStatus_NotImplemented):
                return None  # not supported on this transport/device
            return node.Value()
        except Exception:
            return None  # not readable in current state

    def get_buffer_count(self):
        nm = self.data_stream.NodeMaps()[0]  # DataStream NodeMap
        
        grabbing = nm.FindNode("StreamIsGrabbing").Value()
        delivered = nm.FindNode("StreamDeliveredFrameCount").Value()
        lost      = nm.FindNode("StreamLostFrameCount").Value()
        in_cnt    = nm.FindNode("StreamInputBufferCount").Value()
        out_cnt   = nm.FindNode("StreamOutputBufferCount").Value()
        
        if hasattr(self,"frame_id"):
            frame_id = self.frame_id
        else:
            frame_id=None
        
        if self.debug:
            print(f"grabbing={grabbing} delivered={delivered} lost={lost} in={in_cnt} out={out_cnt} frameID={frame_id}")

        return grabbing, delivered, lost, in_cnt, out_cnt, frame_id
        

    def start_acquisition(self, buffersize=16):

        if self.debug:
            value = self.data_stream.NodeMaps()[0].FindNode("StreamBufferHandlingMode").CurrentEntry().SymbolicValue()
            print("StreamBufferHandlingMode",value)
        nm = self.remote_nodemap
        payload_size = nm.FindNode("PayloadSize").Value()
        min_req = self.data_stream.NumBuffersAnnouncedMinRequired()

        base = max(min_req, int(buffersize))
        buffer_count_max = base + int(base*0.1) # buffer increased by 10%

        for _ in range(buffer_count_max):
            buf = self.data_stream.AllocAndAnnounceBuffer(payload_size)
            self.data_stream.QueueBuffer(buf)

        self.data_stream.StartAcquisition()
        nm.FindNode("AcquisitionStart").Execute()
        nm.FindNode("AcquisitionStart").WaitUntilDone()


    def stop_acquisition(self):

        if self.data_stream.NodeMaps()[0].FindNode("StreamIsGrabbing").Value():
            self.remote_nodemap.FindNode("AcquisitionStop").Execute()
            self.remote_nodemap.FindNode("AcquisitionStop").WaitUntilDone()

            self.data_stream.StopAcquisition(ids_peak.AcquisitionStopMode_Default)
            self.data_stream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)
        else: 
            if self.debug: print("Data stream not running")
        
        for buffer in self.data_stream.AnnouncedBuffers():
            self.data_stream.RevokeBuffer(buffer)

    def get_frame(self, timeout_ms=1000):
        """Gets frame from camera. 
        Use set_stream_mode with values:
        'NewestOnly', 'OldestFirst', 'OldestFirstSingleBuffer','OldestFirstDependOnCameraFIFO'
        to change the streming buffer handling mode.
        """

        buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
        if self.debug:
            self.frame_id = buffer.FrameID()

        ids_image=ids_peak_ipl_extension.BufferToImage(buffer)
        img = numpy.copy(ids_image.get_numpy())
        try:
            self.data_stream.QueueBuffer(buffer)
        except Exception as e:
            if self.debug:
                print(e)
        return img
                

    def set_external_trigger(self, line="Line0", activation="RisingEdge", exposure_mode="Timed"):
        nm = self.remote_nodemap

        # Start frames on trigger events
        nm.FindNode("TriggerSelector").SetCurrentEntry("FrameStart")
        nm.FindNode("TriggerMode").SetCurrentEntry(1)  # On

        # External line as source
        nm.FindNode("TriggerSource").SetCurrentEntry(line)

        # Edge selection (if available on the model)
        try:
            nm.FindNode("TriggerActivation").SetCurrentEntry(activation) # choices: RisingEdge, FallingEdge, AnyEdge, LevelHigh, LevelLow
        except Exception:
            pass  # some models may not expose this; default is typically RisingEdge

        # Exposure behavior
        try:
            nm.FindNode("ExposureMode").SetCurrentEntry(exposure_mode)
        except Exception:
            pass  # not all models support TriggerControlled (Uses one or more trigger signals to control the exposure)

        # Optional: zero trigger delay if present
        try:
            nm.FindNode("TriggerDelay").SetValue(0)
        except Exception:
            pass


    def disable_trigger(self):
        nm = self.remote_nodemap
        nm.FindNode("TriggerSelector").SetCurrentEntry("FrameStart")
        nm.FindNode("TriggerMode").SetValue(0)  # Off

    def set_trigger_source(self, source):
        if source == 'External':
            self.set_external_trigger(line="Line6", activation="RisingEdge")
            print(f'Trigger source is set to External')
        else:
            self.disable_trigger()
            print(f'Trigger source is set to Internal')

    def get_trigger_source(self):
        try:
            nm = self.remote_nodemap
            trigger_source = nm.FindNode("TriggerSource").CurrentEntry().SymbolicValue() # 1 for external
            if trigger_source == 1:
                return 'External'
            else:
                return 'Internal'

        except Exception as e:
            print(f'Error getting trigger source: {e}')

    # New
    def set_trigger_delay(self, delay_ms):
        current_trigger_source = self.get_trigger_source()
        

        frame_rate = self.get_frame_rate()
        period = 1 / frame_rate
        low_time = delay_ms / 1000
        high_time = 1e-3

        if low_time + high_time > period:
            raise ValueError(f'Delay {delay_ms}ms too large for frame rate {frame_rate}Hz')

        try:
            self._stop_trigger_task()

            self._last_trigger_delay = delay_ms
            self._current_frame_rate = frame_rate

            self.trigger_task = nidaqmx.Task()
            output_channel = 'Dev1/port0/line0'

            sample_rate = 250000
            samps_per_period = int(sample_rate * period)
            low_time_samps_n = int(low_time * sample_rate)
            high_time_samps_n = int(high_time * sample_rate)
            remaining_samps = samps_per_period - low_time_samps_n - high_time_samps_n

            trigger_sig = numpy.zeros(samps_per_period, dtype=bool)
            trigger_sig[low_time_samps_n:low_time_samps_n + high_time_samps_n] = True

            self.trigger_task.do_channels.add_do_chan(output_channel)

            self.trigger_task.timing.cfg_samp_clk_timing(
                rate=sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=len(trigger_sig)
            )
            self.trigger_task.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.ALLOW_REGENERATION
            self.trigger_task.write(trigger_sig, auto_start=True)
            self._last_delay = delay_ms

            print(f'Trigger source is set to External with delay: {delay_ms}')

        except Exception as e:
            print(f'Error setting trigger delay: {e}')
            self._stop_trigger_task()

    def _stop_trigger_task(self):
        try:
            self.trigger_task.write(False)
            self.trigger_task.stop()
            self.trigger_task.close()
        except Exception as e:
            print(f'Error stopping trigger task: {e}')

    def get_trigger_delay(self):
        return self._last_delay

    def close(self):
        try:
            self.stop_acquisition()
        except Exception:
            pass
        try:
            self.device.Close()
        except Exception:
            pass

        self._stop_trigger_task()

        try:
            ids_peak.Library.Close()

        except Exception:
            pass


if __name__=="__main__":
    import time
    cam=Camera()
    

    # Determine the current entry of PixelFormat (str)
    nm = cam.remote_nodemap
    value = nm.FindNode("PixelFormat").CurrentEntry().SymbolicValue()
    # Get a list of all available entries of PixelFormat
    
    allEntries = nm.FindNode("PixelFormat").Entries()
    availableEntries = []
    for entry in allEntries:
        if (entry.AccessStatus() != ids_peak.NodeAccessStatus_NotAvailable
                and entry.AccessStatus() != ids_peak.NodeAccessStatus_NotImplemented):
            availableEntries.append(entry.SymbolicValue())
    
    print(availableEntries)
    nm.FindNode("PixelFormat").SetCurrentEntry("Mono8")
    value = nm.FindNode("PixelFormat").CurrentEntry().SymbolicValue()
    value=cam.get_bit_depth()
    print(dir(cam.device))
    print(cam.device.ModelName())

    #value = cam.data_stream.nodeMapDataStream.FindNode("StreamBufferHandlingMode").CurrentEntry().SymbolicValue()
    #print(value)
    # Set PixelFormat to "BayerRG8" (str)
    print(cam.data_stream.NodeMaps()[0].FindNode("StreamBufferHandlingMode").CurrentEntry().SymbolicValue())
    
    cam.debug=True
    
    allEntries = nm.FindNode("AcquisitionMode").Entries()
    availableEntries = []
    for entry in allEntries:
        if (entry.AccessStatus() != ids_peak.NodeAccessStatus_NotAvailable
            and entry.AccessStatus() != ids_peak.NodeAccessStatus_NotImplemented):
            availableEntries.append(entry.SymbolicValue())
    print(availableEntries)

    cam.get_acquisition_mode()
    cam.get_acquisition_mode()
    cam.set_full_chip()

    cam.set_active_region(0, 1712, 512, 600)

    cam.set_width(362)

    cam.get_width()
    cam.get_height()

    is_grabbing = cam.data_stream.NodeMaps()[0].FindNode("StreamIsGrabbing").Value() 
    print(is_grabbing)

    cam.close()

