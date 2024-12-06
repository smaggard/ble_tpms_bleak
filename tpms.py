import asyncio
import time
from bleak import BleakScanner
from bleak.backends.scanner import AdvertisementData
from bleak.backends.device import BLEDevice
import struct
import can
import os
import sys
import logging
from systemd.journal import JournalHandler

# Holley input can ids are as follows.
# For pressure
# Can ID 1575
# Input 1 = Driver Front
# Input 2 = Passenger Front
# Input 3 = Driver Rear
# Input 4 = Passenger Rear
# For Temperature
# Can ID 1575
# Input 5 = Driver Front
# Input 6 = Passenger Front
# Input 7 = Driver Rear
# Input 8 = Passenger Rear
# For Battery
# Can ID 1576
# Input 1 = Driver Front
# Input 2 = Passenger Front
# Input 3 = Driver Rear
# Input 4 = Passenger Rear

# Define devices dictionary
# Each key should be the ID of the sensor in ##:##:##:##:##:## format.
devices_dict = {
        "80:EA:CA:50:2E:D8": {
            "data": "80eaca502ed8580903001c0700005f00", 
            "press_canid": 0x1E202627, 
            "temp_canid": 0x1E212627,
            "batt_canid": 0x1E202628,
            "location": "driver_front"
            },
        "81:EA:CA:50:2E:61": {
            "data": "80eaca502ed8580903001c0700005f00", 
            "press_canid": 0x1E206627,
            "temp_canid": 0x1E216627,
            "batt_canid": 0x1E206628,
            "location": "passenger_front"
            },
        "82:EA:CA:50:2D:18": {
            "data": "80eaca502ed8580903001c0700005f00", 
            "press_canid": 0x1E20A627, 
            "temp_canid": 0x1E21A627,
            "batt_canid": 0x1E20A628,
            "location": "driver_rear"
            },
        "83:EA:CA:50:2D:34": {
            "data": "80eaca502ed8580903001c0700005f00", 
            "press_canid": 0x1E20E627, 
            "temp_canid": 0x1E21E627,
            "batt_canid": 0x1E20E628,
            "location": "passenger_rear"
            }
}

# Setup logging to log to journald
log = logging.getLogger('tpms')
log.addHandler(JournalHandler())
log.setLevel(logging.INFO)

# Setup Can bus
bus = can.interface.Bus(channel='can0', interface='socketcan', receive_own_messages=True)

# Start sub routines
def hex2int(_HEX):
  _BIN=bytes.fromhex(_HEX)
  _Rev=_BIN[::-1]
  _HEX=_Rev.hex()
  return int(_HEX,16)

def is_divisible_by_5(count):
  return count % 5 == 0

# Convert value to required scale
def remap( x, oMin, oMax, nMin, nMax ):
    oldMin = min( oMin, oMax )
    oldMax = max( oMin, oMax )
    newMin = min( nMin, nMax )
    newMax = max( nMin, nMax )
    portion = (x-oldMin)*(newMax-newMin)/(oldMax-oldMin)
    result = portion + newMin
    return result

# Convert floating point to hex.
def float_to_hex(f):
    return hex(struct.unpack('<I', struct.pack('<f', f))[0])

# Convert a Hex Value to floating point.
def hex_to_float(f):
    return struct.unpack('!f',bytes.fromhex(f))[0]

# Create Can message
def create_can_message(canid,data):
    # Form CAN message 
    return can.Message(arbitration_id=canid,data=data, is_extended_id=True)

# Convert hex string into a byte array for use in a CAN message
def create_dlc(x):
    # Create byte array from string
    return [int('0x'+x[2]+x[3], 16),int('0x'+x[4]+x[5], 16),int('0x'+x[6]+x[7], 16),int('0x'+x[8]+x[9], 16)]

# Send CAN message and bounce interface if it fails
def send_msg(msg):
    try:
        bus.send(msg)
        return True
    except Exception as e:
        log.error(e)
        # Bouncing Can network.
        bounce_interface()

# Bounce Interfaces
def bounce_interface():
    try:
        # Log bounce
        log.error("Bouncing Can interface due to error")
        # Bounce Interface
        os.system("ifdown can0")
        os.system("ifup can0")
        time.sleep(.5)
        # Recreate bus
        global bus 
        bus = can.interface.Bus(channel='can0', interface='socketcan', receive_own_messages=True)
        return True
    except Exception as e:
        log.error(e)
# End sub ruitines


async def main(devices_dict):
    count = 0
    while True:
        if is_divisible_by_5(count):
            # Scan bluetooth for 5 seconds
            log.info("Scanning bluetooth to update values")
            devices = await BleakScanner.discover(return_adv=True,timeout=5)
            # Iterate over devices from scan looking for the known tpms sensors
            for device in devices.values():
                # Pull identity and data from device
                identity = device[0].address
                data = device[1].manufacturer_data
                # If identity isn't a known sensor skip processing.
                if identity not in devices_dict.keys():
                    continue
                else:
                    man_data = data[0x0100].hex()
                    if len(man_data) == 32:
                        devices_dict[identity]["data"] = man_data
        
        for identity in devices_dict:        
            # Get the proper bytes for each portion
            pressure = devices_dict[identity]['data'][12:18]
            temp = devices_dict[identity]['data'][20:24]
            bat = devices_dict[identity]['data'][28:30]
            
            # Convert bytes into floats in proper format
            pressurePSI = round((hex2int(pressure)/100000)*14.5037738,2)
            tempF = round((hex2int(temp)/100)*1.8 +32,2)
            batt = hex2int(bat)
                    
            # Remap to 5v for sending to Holley ECU
            remapped_press = remap(pressurePSI, 0, 50, 0, 5)
            remapped_temp = remap(tempF, 0, 212, 0, 5)
            remapped_batt = remap(batt, 0, 100, 0, 5)
                    
            # Create Messages
            press_msg = create_can_message(devices_dict[identity]["press_canid"],create_dlc(float_to_hex(remapped_press)))
            temp_msg = create_can_message(devices_dict[identity]["temp_canid"],create_dlc(float_to_hex(remapped_temp)))
            batt_msg = create_can_message(devices_dict[identity]["batt_canid"],create_dlc(float_to_hex(remapped_batt)))

            # Send Messages
            log.info(f"Sending {devices_dict[identity]['location']}: Pressure {pressurePSI}, Temperature {tempF}, Battery % {batt}")
            send_msg(press_msg)
            send_msg(temp_msg)
            send_msg(batt_msg)
            # Increment count
            count = count+1
            # Sleep 1
            time.sleep(1)
                    

if __name__ == "__main__":
    try:
        log.info("Starting main application")
        asyncio.run(main(devices_dict))

    except KeyboardInterrupt:
        log.info('Interrupted')
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)
