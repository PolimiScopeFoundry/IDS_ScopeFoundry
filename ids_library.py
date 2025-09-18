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

    def set_debug_mode(self, value):
        self.debug = value

    def get_debug_mode(self):
        return self.debug

    def get_model(self):
        return self.device.ModelName()

    def get_width(self):
        w_h = self.get_size()
        return w_h[0] 


    def get_height(self):
        w_h = self.get_size()
        return w_h[1]

    def get_size(self):
        return(self.remote_nodemap.FindNode("SensorWidth").Value(),self.remote_nodemap.FindNode("SensorHeight").Value())

    def set_node_value(self,name,value):
        if value<self.remote_nodemap.FindNode(name).Minimum():
            self.remote_nodemap.FindNode(name).SetValue(
                self.remote_nodemap.FindNode(name).Minimum())
        elif value>self.remote_nodemap.FindNode(name).Maximum():
            self.remote_nodemap.FindNode(name).SetValue(
                self.remote_nodemap.FindNode(name).Maximum())
        else:
            self.remote_nodemap.FindNode(name).SetValue(value)

    def set_full_chip(self):
        self.remote_nodemap.FindNode("OffsetX").SetValue(0)
        self.remote_nodemap.FindNode("OffsetY").SetValue(0)
        self.remote_nodemap.FindNode("Width").SetValue(
            self.remote_nodemap.FindNode("Width").Maximum())
        self.remote_nodemap.FindNode("Height").SetValue(
            self.remote_nodemap.FindNode("Height").Maximum())

    def set_active_region(self,x,y,w,h):
        self.remote_nodemap.FindNode("OffsetX").SetValue(0)
        self.remote_nodemap.FindNode("OffsetY").SetValue(0)

        self.set_node_value("Width",w)
        self.set_node_value("Height", h)
        self.set_node_value("OffsetX",x)
        self.set_node_value("OffsetY", y)
            
    def get_frame_rate(self):
        val = self.remote_nodemap.FindNode("AcquisitionFrameRate").Value()
        if self.debug: print("Frame rate:", val, "fps")
        return val
    
    def set_frame_rate(self,framerate):
        max_rate = self.remote_nodemap.FindNode("AcquisitionFrameRate").Maximum()
        self.set_node_value("AcquisitionFrameRate", min(framerate, max_rate))
        if self.debug: self.get_frame_rate

    def get_exposure_ms(self):
        val = self.remote_nodemap.FindNode("ExposureTime").Value()/1000
        if self.debug: print("Exposure time:", val, "ms")
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
        if self.debug: self.get_gain()

    def get_gain(self):
        val = self.remote_nodemap.FindNode("Gain").Value()
        if self.debug: print("Gain:", val)
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
        if self.debug: self.get_bit_depth()

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
                if self.debug: print("Bit depth:", key)
                return key

    def set_frame_num(self, nframes):
        nm = self.remote_nodemap
        nm.FindNode("AcquisitionMode").SetCurrentEntry("MultiFrame")
        nm.FindNode("AcquisitionFrameCount").SetValue(int(nframes))

    def start_acquisition(self, buffersize=64):
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
        self.remote_nodemap.FindNode("AcquisitionStop").Execute()
        self.remote_nodemap.FindNode("AcquisitionStop").WaitUntilDone()

        self.data_stream.StopAcquisition(ids_peak.AcquisitionStopMode_Default)
        self.data_stream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)
        for buffer in self.data_stream.AnnouncedBuffers():
            self.data_stream.RevokeBuffer(buffer)

    
    def get_live_frame(self, timeout_ms=0, fallback_ms=1000):
        """
        Return the most recent finished frame already available.
        Drains ready buffers, keeps only the newest one, copies once.
        If none are ready, block for exactly one fresh frame.
        """
        last_buf = None

        # Drain any ready buffers; keep only the newest unqueued
        while True:
            try:
                buf = self.data_stream.WaitForFinishedBuffer(timeout_ms)
                if buf is None:
                    break
                if last_buf is not None:
                    self.data_stream.QueueBuffer(last_buf)
                last_buf = buf
            except Exception:
                break

        if last_buf is not None:
            try:
                img = numpy.copy(ids_peak_ipl_extension.BufferToImage(last_buf).get_numpy())
            finally:
                self.data_stream.QueueBuffer(last_buf)
            return img

        # Nothing ready: block for one fresh buffer
        buf = self.data_stream.WaitForFinishedBuffer(max(fallback_ms, 1))
        if buf is None:
            raise TimeoutError("No frame available")
        try:
            img = numpy.copy(ids_peak_ipl_extension.BufferToImage(buf).get_numpy())
        finally:
            self.data_stream.QueueBuffer(buf)
        return img


    def get_frame(self, timeout_ms=1000):
        buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
        ids_image=ids_peak_ipl_extension.BufferToImage(buffer)
        img = numpy.copy(ids_image.get_numpy())
        self.data_stream.QueueBuffer(buffer)
        return img


    def get_last_frame(self, timeout_ms=1000):
        buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
        indexes = []
        buffers= self.data_stream.AnnouncedBuffers() #AnnouncedBuffers() includes buffers in various states (queued, filling, finished). The “max FrameID” buffer might not be finished 
        for buf in self.data_stream.AnnouncedBuffers():
            indexes.append(buf.FrameID())
        ids_image = ids_peak_ipl_extension.BufferToImage(buffers[int(numpy.argmax(numpy.asarray(indexes)))])
        img = numpy.copy(ids_image.get_numpy())
        self.data_stream.QueueBuffer(buffer)
        return img
    
    
    def get_multiple_frames(self, nframes, timeout_ms=1000):
        for _ in range(nframes):
            buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
            img = numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
            self.data_stream.QueueBuffer(buffer)
            yield img
            

    def set_external_trigger(self, line="Line0", activation="RisingEdge", exposure_mode="Timed"):
        nm = self.remote_nodemap

        # Start frames on trigger events
        nm.FindNode("TriggerSelector").SetCurrentEntry("FrameStart")
        nm.FindNode("TriggerMode").SetValue(1)  # On

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


    def close(self):
        try:
            self.stop_acquisition()
        except Exception:
            pass
        try:
            self.device.Close()
        except Exception:
            pass
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
    
    # Set PixelFormat to "BayerRG8" (str)
        

    
    
    cam.close()

