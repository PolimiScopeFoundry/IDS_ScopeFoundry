from ids_peak import ids_peak
from ids_peak import ids_peak_ipl_extension
import warnings
import numpy


class Camera:
    def __init__(self, cam_num=0):
        ids_peak.Library.Initialize()
        device_manager = ids_peak.DeviceManager.Instance()
        device_manager.Update()
        self.device = device_manager.Devices()[cam_num].OpenDevice(ids_peak.DeviceAccessType_Control)
        # Nodemap for accessing GenICam nodes
        self.remote_nodemap = self.device.RemoteDevice().NodeMaps()[0]
        self.data_stream = self.device.DataStreams()[0].OpenDataStream()

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


    def get_exposure_ms(self):
        val = self.remote_nodemap.FindNode("ExposureTime").Value()/1000
        print(val)
        return val
            

    def get_frame_rate(self):
        val = self.remote_nodemap.FindNode("AcquisitionFrameRate").Value()
        print(val)
        return val


    def set_exposure_ms(self,value):
        value=value*1000
        self.set_node_value("ExposureTime",value)
        max_exposure = self.remote_nodemap.FindNode("ExposureTime").Maximum()
        print(value, max_exposure)
        if value > max_exposure: 
            self.remote_nodemap.FindNode("AcquisitionFrameRate").SetValue(
                self.remote_nodemap.FindNode("AcquisitionFrameRate").Maximum())
        
    def set_frame_rate(self,framerate):
        max_rate = self.remote_nodemap.FindNode("AcquisitionFrameRate").Maximum()
        self.set_node_value("AcquisitionFrameRate", min(framerate, max_rate))
        print(self.remote_nodemap.FindNode("AcquisitionFrameRate").Value())


    def set_gain(self,value):
        self.set_node_value("Gain",value)


    def set_bit_depth(self,value):
        if value==8:
            self.remote_nodemap.FindNode("PixelFormat").SetCurrentEntry(self.remote_nodemap.FindNode("PixelFormat").Entries()[0])
        elif value==10:
            self.remote_nodemap.FindNode("PixelFormat").SetCurrentEntry(self.remote_nodemap.FindNode("PixelFormat").Entries()[3])
        elif value==12:
            self.remote_nodemap.FindNode("PixelFormat").SetCurrentEntry(self.remote_nodemap.FindNode("PixelFormat").Entries()[4])
        else:
            warnings.warn("Invalid bit depth")


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


    def get_live_frame(self, timeout_ms=1):
        """
        Return the most recent finished frame for live view.
        Drains any currently-finished buffers (discarding older frames),
        copies the newest image, and re-queues all drained buffers.
        """
        last_img = None

        # Drain everything that's immediately ready; keep only the newest copy
        while True:
            try:
                buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
                try:
                    last_img = numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
                finally:
                    # Always re-queue to avoid starving the stream
                    self.data_stream.QueueBuffer(buffer)
                # loop again with short timeout to see if an even newer one is ready
                continue
            except Exception:
                # No more finished buffers within timeout_ms
                break

        # If nothing was ready, block briefly to fetch at least one fresh frame
        if last_img is None:
            
            buffer = self.data_stream.WaitForFinishedBuffer(max(timeout_ms, 1000))
            try:
                last_img = numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
            finally:
                self.data_stream.QueueBuffer(buffer)
        return last_img
    

    def get_frame(self, timeout_ms=1000):
        buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
        ids_image=ids_peak_ipl_extension.BufferToImage(buffer)
        img = numpy.copy(ids_image.get_numpy())
        self.data_stream.QueueBuffer(buffer)
        return img


    def get_last_frame(self, timeout_ms=1000):
        buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
        indexes = []
        buffers= self.data_stream.AnnouncedBuffers()
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
    cam.set_bit_depth(10)
    cam.set_full_chip()
    # cam.set_active_region(300,900,300,300)

    cam.set_exposure_ms(1.0)
    cam.set_frame_rate(100)
    cam.set_gain(10.0)

    N=100
    
    cam.remote_nodemap.FindNode("AcquisitionMode").SetCurrentEntry("Continuous")
    cam.start_acquisition(int(N))

    cam.get_live_frame()

    t = time.perf_counter()
    
    cam.stop_acquisition()

    
    cam.close()

