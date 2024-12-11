""" Application to pull the Pressure, temperature and battery
Levels from Bluetooth TPMS sensors located on cars tires
and send the values to a Holley Terminator X or dominator.
"""
import asyncio
import logging
import os
import struct
import sys
import time
import can
from bleak import BleakScanner
from systemd.journal import JournalHandler # pylint: disable=import-error

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
def hex2int(_hex):
    """ Cover a hex into an int
    
    Keyword arguments:
    _hex (bytes): A hex number you need converted to an integer

    Returns:
    int(int): the Hex converted to base16
    """
    _bin=bytes.fromhex(_hex)
    _rev=_bin[::-1]
    _hex=_rev.hex()
    return int(_hex,16)

def is_divisible_by_5(count):
    """ Check if number is divisible by 5
    
    Keyword arguments:
    count(int): A number to check if divisible by 5

    Returns:
    (bool): Is/Is Not divisible
    """
    return count % 5 == 0

# Convert value to required scale
def remap( x, omin, omax, nmin, nmax ):
    """ Scale a float from one scale to another
    
    Keyword arguments:
    x(float): Number to Scale
    omin(float): Old Minimum
    omax(float): Old Maximum
    nmin(float): New Minimum
    nmax(float): New Maximum

    Returns:
    (float) -- rescaled float value
    """
    old_min = min( omin, omax )
    old_max = max( omin, omax )
    new_min = min( nmin, nmax )
    new_max = max( nmin, nmax )
    portion = (x-old_min)*(new_max-new_min)/(old_max-old_min)
    result = portion + new_min
    return result

# Convert floating point to hex.
def float_to_hex(f):
    """ Convert a float to a hex number
    
    Keyword arguments:
    f(float): Number to covert

    Returns:
    (hex) -- Converted value
    """
    return hex(struct.unpack('<I', struct.pack('<f', f))[0])

# Convert a Hex Value to floating point.
def hex_to_float(f):
    """ Convert a Hex to a float value
    
    Keyword arguments:
    f(bytes): Number to covert

    Returns:
    (float) -- Converted value
    """
    return struct.unpack('!f',bytes.fromhex(f))[0]

# Create Can message
def create_can_message(canid,data):
    """ Convert a float to a hex number
    
    Keyword arguments:
    canid(int): Can id to send message to.
    data(bytearray): Data to send

    Returns:
    (can.Message) -- Can message to send
    """
    # Form CAN message.
    return can.Message(arbitration_id=canid,data=data, is_extended_id=True)

# Convert hex string into a byte array for use in a CAN message
def create_dlc(x):
    """ Create a 4 Byte data packet to send across the can bus.
    
    Keyword arguments:
    x(str): Message to convert
    
    Returns:
    (bytearray): A byte array representation of the DLC
    """
    # Create byte array from string
    return [int('0x'+x[2]+x[3], 16),int('0x'+x[4]+x[5], 16),
            int('0x'+x[6]+x[7], 16),int('0x'+x[8]+x[9], 16)]

# Send CAN message and bounce interface if it fails
def send_msg(msg):
    """ Send Can message
    
    Keyword arguments:
    msg(can.Message): Can message to send
    
    Returns:
    (bool)
    """
    try:
        bus.send(msg)
        return True
    except can.exceptions.CanOperationError as e:
        log.error(e)
        # Bouncing Can network.
        bounce_interface()
        return False

# Bounce Interfaces
def bounce_interface():
    """Bounce CAN interface"""
    # pylint: disable=global-statement
    # pylint: disable=broad-exception-caught
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
        return False
# End sub ruitines


async def main(devices_dict):
    """ Main subroutine, Scans bluetooth ever 10 seconds and sends can messages every second
    
        Keyword arguments:
        devices_dict(dict): Dictionary of devices to scan for and decipher

        Returns: None
    """
    # pylint: disable=redefined-outer-name
    # pylint: disable=too-many-locals
    # pylint: disable=logging-fstring-interpolation
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
                    pass
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
            pressures_psi = round((hex2int(pressure)/100000)*14.5037738,2)
            temp_f = round((hex2int(temp)/100)*1.8 +32,2)
            batt = hex2int(bat)

            # Remap to 5v for sending to Holley ECU
            remapped_press = remap(pressures_psi, 0, 50, 0, 5)
            remapped_temp = remap(temp_f, 0, 212, 0, 5)
            remapped_batt = remap(batt, 0, 100, 0, 5)

            # Create Messages
            press_msg = create_can_message(devices_dict[identity]["press_canid"],
                                           create_dlc(float_to_hex(remapped_press)))
            temp_msg = create_can_message(devices_dict[identity]["temp_canid"],
                                          create_dlc(float_to_hex(remapped_temp)))
            batt_msg = create_can_message(devices_dict[identity]["batt_canid"],
                                          create_dlc(float_to_hex(remapped_batt)))

            # Send Messages
            log.info(f"""Sending {devices_dict[identity]['location']}:
                     Pressure {pressures_psi}, Temperature {temp_f}, Battery % {batt}""")
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
