import sys
from ids_peak import ids_peak as peak
 
m_device = None
m_dataStream = None
m_node_map_remote_device = None
 
 
def open_camera():
   global m_device, m_node_map_remote_device
   try:
      # Create instance of the device manager
       device_manager = peak.DeviceManager.Instance()
      # Update the device manager
       device_manager.Update()
 
      # Return if no device was found
       if device_manager.Devices().empty():
           return False
 
      # open the first openable device in the device manager's device list
       device_count = device_manager.Devices().size()
       for i in range(device_count):
           if device_manager.Devices()[i].IsOpenable():
               m_device = device_manager.Devices()[i].OpenDevice(peak.DeviceAccessType_Control)
 
              # Get NodeMap of the RemoteDevice for all accesses to the GenICam NodeMap tree
               m_node_map_remote_device = m_device.RemoteDevice().NodeMaps()[0]
 
               return True
   except Exception as e:
      # ...
       str_error = str(e)
 
   return False
 
 
def prepare_acquisition():
   global m_dataStream
   try:
       data_streams = m_device.DataStreams()
       if data_streams.empty():
          # no data streams available
           return False
 
       m_dataStream = m_device.DataStreams()[0].OpenDataStream()
 
       return True
   except Exception as e:
      # ...
       str_error = str(e)
 
   return False
 
 
def set_roi(x, y, width, height):
   try:
      # Get the minimum ROI and set it. After that there are no size restrictions anymore
       x_min = m_node_map_remote_device.FindNode("OffsetX").Minimum()
       y_min = m_node_map_remote_device.FindNode("OffsetY").Minimum()
       w_min = m_node_map_remote_device.FindNode("Width").Minimum()
       h_min = m_node_map_remote_device.FindNode("Height").Minimum()
 
       m_node_map_remote_device.FindNode("OffsetX").SetValue(x_min)
       m_node_map_remote_device.FindNode("OffsetY").SetValue(y_min)
       m_node_map_remote_device.FindNode("Width").SetValue(w_min)
       m_node_map_remote_device.FindNode("Height").SetValue(h_min)
 
      # Get the maximum ROI values
       x_max = m_node_map_remote_device.FindNode("OffsetX").Maximum()
       y_max = m_node_map_remote_device.FindNode("OffsetY").Maximum()
       w_max = m_node_map_remote_device.FindNode("Width").Maximum()
       h_max = m_node_map_remote_device.FindNode("Height").Maximum()
 
       if (x < x_min) or (y < y_min) or (x > x_max) or (y > y_max):
           return False
       elif (width < w_min) or (height < h_min) or ((x + width) > w_max) or ((y + height) > h_max):
           return False
       else:
          # Now, set final AOI
           m_node_map_remote_device.FindNode("OffsetX").SetValue(x)
           m_node_map_remote_device.FindNode("OffsetY").SetValue(y)
           m_node_map_remote_device.FindNode("Width").SetValue(width)
           m_node_map_remote_device.FindNode("Height").SetValue(height)
 
           return True
   except Exception as e:
      # ...
       str_error = str(e)
 
   return False
 
 
def alloc_and_announce_buffers():
    try:
       if m_dataStream:
          # Flush queue and prepare all buffers for revoking
           m_dataStream.Flush(peak.DataStreamFlushMode_DiscardAll)
 
          # Clear all old buffers
           for buffer in m_dataStream.AnnouncedBuffers():
               m_dataStream.RevokeBuffer(buffer)
 
           payload_size = m_node_map_remote_device.FindNode("PayloadSize").Value()
 
          # Get number of minimum required buffers
           num_buffers_min_required = m_dataStream.NumBuffersAnnouncedMinRequired()
 
          # Alloc buffers
           for count in range(num_buffers_min_required):
               buffer = m_dataStream.AllocAndAnnounceBuffer(payload_size)
               m_dataStream.QueueBuffer(buffer)
 
           return True
    except Exception as e:
      # ...
       str_error = str(e)
 
    return False
 
 
def start_acquisition():
    try:
       m_dataStream.StartAcquisition(peak.AcquisitionStartMode_Default, peak.DataStream.INFINITE_NUMBER)
       m_node_map_remote_device.FindNode("TLParamsLocked").SetValue(1)
       m_node_map_remote_device.FindNode("AcquisitionStart").Execute()
       
       return True
    except Exception as e:
      # ...
       str_error = str(e)
 
    return False
 
 
def main():
  # initialize library
   peak.Library.Initialize()
 
   if not open_camera():
      # error
       sys.exit(-1)
 
   if not prepare_acquisition():
      # error
       sys.exit(-2)
 
   if not set_roi(16, 16, 128, 128):
      # error
       sys.exit(-3)
 
   if not alloc_and_announce_buffers():
      # error
       sys.exit(-4)
 
   if not start_acquisition():
      # error
       sys.exit(-5)
 
   peak.Library.Close()
   sys.exit(0)
 
 
if __name__ == '__main__':
   main()
