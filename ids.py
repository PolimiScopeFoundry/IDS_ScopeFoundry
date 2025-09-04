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


    def start_acquisition(self, buffersize=0):
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

    def get_frame(self, timeout_ms=1000):
        buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
        try:
            return numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
        finally:
            self.data_stream.QueueBuffer(buffer)
        return img

    def get_last_frame(self, timeout_ms=1):
        """Get the most recent finished buffer by draining the queue quickly."""
        last_img = None
        while True:
            try:
                buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
                try:
                    last_img = numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
                finally:
                    self.data_stream.QueueBuffer(buffer)
                # loop again to see if a newer one is already ready
            except Exception:
                break
        if last_img is None:
            # fall back to a normal wait
            buffer = self.data_stream.WaitForFinishedBuffer(max(timeout_ms, 1000))
            try:
                return numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
            finally:
                self.data_stream.QueueBuffer(buffer)
        return last_img
    
    def get_multiple_frames(self, nframes, timeout_ms=1000):
        for _ in range(nframes):
            buffer = self.data_stream.WaitForFinishedBuffer(timeout_ms)
            try:
                img = numpy.copy(ids_peak_ipl_extension.BufferToImage(buffer).get_numpy())
                yield img
            finally:
                self.data_stream.QueueBuffer(buffer)
    
    def enable_frame_event_timestamps(self):
        nm = self.remote_nodemap
        for ev in ("FrameStart", "ExposureStart", "ExposureEnd"):
            try:
                nm.FindNode("EventSelector").SetCurrentEntry(ev)
                nm.FindNode("EventNotification").SetCurrentEntry("On")
            except Exception:
                pass  # skip if not supported on your model


    def get_multiple_frames_with_device_ts(self, nframes, timeout_ms=1000, prefer_event="FrameStart"):
        """
        Yield (img, ts_ns, frame_id, ts_source) for nframes.
        Timestamp priority: Buffer TS -> Chunk TS -> Event TS (FrameStart/ExposureStart/ExposureEnd).
        Automatically enables ChunkMode or Events if available.
        """
        nm = self.remote_nodemap

        # --- one-time lazy setup flags (per call) ---
        tried_enable_chunk = False
        tried_enable_events = False

        # helpers ---------------------------------------------------------------
        def _try_buffer_timestamp(buf):
            # various SDKs expose different names; try a few
            for name in ("Timestamp", "TimestampNs", "GetTimestamp", "GetTimestampNs"):
                if hasattr(buf, name):
                    try:
                        val = getattr(buf, name)()
                        return int(val), "buffer"
                    except Exception:
                        pass
            return None, None

        def _try_chunk_timestamp(buf, img_obj):
            nonlocal tried_enable_chunk
            # enable ChunkMode (only once)
            if not tried_enable_chunk:
                tried_enable_chunk = True
                try:
                    nm.FindNode("ChunkModeActive").SetValue(1)
                    nm.FindNode("ChunkSelector").SetCurrentEntry("Timestamp")
                    nm.FindNode("ChunkEnable").SetValue(1)
                    # optional: also enable FrameID chunk if present
                    try:
                        nm.FindNode("ChunkSelector").SetCurrentEntry("FrameID")
                        nm.FindNode("ChunkEnable").SetValue(1)
                    except Exception:
                        pass
                except Exception:
                    pass  # chunk not supported; we'll just fail over

            # Try on buffer first, then on image object (bindings vary)
            candidates = [(buf, ("ChunkTimestamp", "GetChunkTimestamp", "Timestamp")),
                        (img_obj, ("ChunkTimestamp", "GetChunkTimestamp", "Timestamp"))]
            for obj, names in candidates:
                for name in names:
                    if hasattr(obj, name):
                        try:
                            val = getattr(obj, name)()
                            return int(val), "chunk"
                        except Exception:
                            pass
            return None, None

        def _enable_events_once():
            # turn on events we can use
            for ev in ("FrameStart", "ExposureStart", "ExposureEnd"):
                try:
                    nm.FindNode("EventSelector").SetCurrentEntry(ev)
                    nm.FindNode("EventNotification").SetCurrentEntry("On")
                except Exception:
                    pass

        def _try_event_timestamp(frame_id):
            nonlocal tried_enable_events
            if not tried_enable_events:
                tried_enable_events = True
                try:
                    _enable_events_once()
                except Exception:
                    pass

            # Which event do you prefer to time-stamp the frame with?
            order = {
                "FrameStart": ("EventFrameStartFrameID", "EventFrameStartTimestamp"),
                "ExposureStart": ("EventExposureStartFrameID", "EventExposureStartTimestamp"),
                "ExposureEnd": ("EventExposureEndFrameID", "EventExposureEndTimestamp"),
            }
            # build preference list with fallbacks
            pref = [prefer_event] + [k for k in ("FrameStart", "ExposureStart", "ExposureEnd") if k != prefer_event]

            for key in pref:
                ids_node, ts_node = order[key]
                try:
                    eid = nm.FindNode(ids_node).Value()
                    if int(eid) == int(frame_id):
                        ts = nm.FindNode(ts_node).Value()
                        return int(ts), f"event:{key}"
                except Exception:
                    continue
            return None, None
        # ----------------------------------------------------------------------

        for _ in range(nframes):
            buf = self.data_stream.WaitForFinishedBuffer(timeout_ms)
            try:
                frame_id = None
                try:
                    frame_id = buf.FrameID()
                except Exception:
                    pass

                # Convert to image (needed for chunk attempts anyway)
                img_obj = ids_peak_ipl_extension.BufferToImage(buf)
                img = numpy.copy(img_obj.get_numpy())

                # 1) buffer timestamp
                ts, src = _try_buffer_timestamp(buf)
                if ts is not None:
                    yield img, ts, frame_id, src
                    continue

                # 2) chunk timestamp
                ts, src = _try_chunk_timestamp(buf, img_obj)
                if ts is not None:
                    yield img, ts, frame_id, src
                    continue

                # 3) event timestamp (match by FrameID if we got one)
                if frame_id is not None:
                    ts, src = _try_event_timestamp(frame_id)
                    if ts is not None:
                        yield img, ts, frame_id, src
                        continue

                # Fallback: no device timestamp found
                yield img, None, frame_id, "none"
            finally:
                self.data_stream.QueueBuffer(buf)



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
    cam.enable_frame_event_timestamps()
    cam.start_acquisition(int(N))

    t = time.perf_counter()
    for frame_idx, (img, ts_ns, fid, src) in enumerate(cam.get_multiple_frames_with_device_ts(N)):
        #dt = time.perf_counter() - t
        #print(f"Frame {frame_idx}: shape={img.shape}, Δt={dt:.4f}s")
        if frame_idx==0:
            t0=ts_ns

        print(f"#{frame_idx:03d}  fid={fid}  ts={(ts_ns-t0)/1000000} ms  src={src}, shape={img.shape}")
        #t = time.perf_counter()

    cam.stop_acquisition()
    #cam.stop_acquisition()

    # for node in cam.remote_nodemap.Nodes():
    #    print(node.Name())

    
    cam.close()

