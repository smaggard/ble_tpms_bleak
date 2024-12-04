import asyncio
import time
from bleak import BleakScanner
import struct
import can
import os
import sys

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

devices_dict = {
        "F4:BC:DA:32:70:35": {
            "data": "000181EACA108A78E36D0000E60A00005B00", 
            "press_canid": 0x1E202627, 
            "temp_canid": 0x1E212627,
            "batt_canid": 0x1E202628,
            "location": "driver_front"
            },
        "F4:BC:DA:32:70:90": {
            "data": "000180EACA108A78E36D0000E60A00005B00", 
            "press_canid": 0x1E206627,
            "temp_canid": 0x1E216627,
            "batt_canid": 0x1E206628,
            "location": "passenger_front"
            },
        "F4:BC:DA:32:70:35": {
            "data": "000181EACA108A78E36D0000E60A00005B00", 
            "press_canid": 0x1E20A627, 
            "temp_canid": 0x1E21A627,
            "batt_canid": 0x1E20A628,
            "location": "driver_rear"
            },
        "F4:BC:DA:32:70:35": {
            "data": "000181EACA108A78E36D0000E60A00005B00", 
            "press_canid": 0x1E20E627, 
            "temp_canid": 0x1E21E627,
            "batt_canid": 0x1E20E628,
            "location": "passenger_rear"
            }
}

def hex2int(_HEX):
  _BIN=bytes.fromhex(_HEX)
  _Rev=_BIN[::-1]
  _HEX=_Rev.hex()
  return int(_HEX,16)

def remap( x, oMin, oMax, nMin, nMax ):

    #range check
    if oMin == oMax:
        print("Warning: Zero input range")
        return None

    if nMin == nMax:
        print("Warning: Zero output range")
        return None

    #check reversed input range
    reverseInput = False
    oldMin = min( oMin, oMax )
    oldMax = max( oMin, oMax )
    if not oldMin == oMin:
        reverseInput = True

    #check reversed output range
    reverseOutput = False   
    newMin = min( nMin, nMax )
    newMax = max( nMin, nMax )
    if not newMin == nMin :
        reverseOutput = True

    portion = (x-oldMin)*(newMax-newMin)/(oldMax-oldMin)
    if reverseInput:
        portion = (oldMax-x)*(newMax-newMin)/(oldMax-oldMin)

    result = portion + newMin
    if reverseOutput:
        result = newMax - portion

    return result

def float_to_hex(f):
    return hex(struct.unpack('<I', struct.pack('<f', f))[0])

def hex_to_float(f):
    return struct.unpack('!f',bytes.fromhex(f))[0]

def create_can_message(canid,data):
    return can.Message(arbitration_id=canid,data=data, is_extended_id=True)

def create_dlc(x):
    return [int('0x'+x[2]+x[3], 16),int('0x'+x[4]+x[5], 16),int('0x'+x[6]+x[7], 16),int('0x'+x[8]+x[9], 16)]

def send_msg(msg):
    try:
        bus.send(msg)
        return True
    except:
        return False
    
async def main(devices_dict):
    while True:
        devices = await BleakScanner.discover(return_adv=True,timeout=4)
        for device in devices.values():
            identity = device[0].address
            data = device[1].manufacturer_data
            if identity not in devices_dict.keys():
                continue
            else:
                for key in data:
                    man_data = data[key].hex()
                    print(man_data)
                    print(len(man_data))
                    if len(man_data) == 30:
                        devices_dict[identity]["data"] = man_data
                    else:
                        next
                    # Get the proper bytes for each portion
                    pressure = devices_dict[identity]['data'][16:22]
                    temp = devices_dict[identity]['data'][24:28]
                    bat = devices_dict[identity]['data'][32:36]
                    
                    # Convert bytes into floats in proper format
                    pressurePSI = round((hex2int(pressure)/100000)*14.5037738,2)
                    tempF = round((hex2int(temp)/100)*1.8 +32,2)
                    batt = hex2int(bat)
                    
                    print(pressurePSI)
                    print(tempF)
                    print(batt)
                    
                    # Remap to 5v for sending to Holley ECU
                    remapped_press = remap(pressurePSI, 0, 50, 0, 5)
                    remapped_temp = remap(tempF, 0, 212, 0, 5)
                    remapped_batt = remap(batt, 0, 100, 0, 5)
                    
                    # Create Messages
                    press_msg = create_can_message(devices_dict[identity]["press_canid"],create_dlc(float_to_hex(remapped_press)))
                    temp_msg = create_can_message(devices_dict[identity]["temp_canid"],create_dlc(float_to_hex(remapped_temp)))
                    batt_msg = create_can_message(devices_dict[identity]["batt_canid"],create_dlc(float_to_hex(remapped_batt)))

                    # Send Messages
                    #send_msg(press_msg)
                    #send_msg(temp_msg)
                    #send_msg(batt_msg)
                    
                    # Send Messages
            print("End Run")

if __name__ == "__main__":
    try:
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        asyncio.run(main(devices_dict))

    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)
