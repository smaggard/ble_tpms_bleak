# ble_tpms_bleak
TPMS system that will send messages to a Holley Terminator X or Dominator as a Can I/O module.

This application is written to be ran on a Raspberry Pi (Pi4 8GB used for Testing), along with 
CAN Hat https://www.amazon.com/gp/product/B07VMB1ZKH and TPMS sensors https://www.amazon.com/dp/B0DBPLD1MQ

After installing the sensors on the tires you will directly after need to run the following command on the 
raspberry pi in close proximity to the car.
```
bluetoothclt
scan le
```
Then watch for the 4 devices that start with 80, 81, 82 and 83, those sensors will align to sensor 1,2,3,and 4 respectively.
Enter those id's as the keys for devices_dict dictionary in tpms.py. then stop scanning and exit by running 
```
scan off
exit
```

# Installation
## Modify tpms.py file.
Edit tpms.py file and change the Keys of the devices dict to match your TPMS sensors.
## Copy files to directoryies
```
cp tpms.service /etc/systemd/system/
mkdir /opt/tpms
cp tpms.py requirements.txt /opt/tpms/
cd /opt/tpms/
# Create Virtual Env
python3 -m venv .
source bin/activate
# Install requirements
pip3 install -r requirements.txt
```
##
Start Service
```systemctl start tpms```
```systemctl enable tpms```

# Holley EFI Setup
Each wheel TPMS will use up to 3 inputs, its up to you how many of them you use.
The inputs will be Pressure in PSI, Temperature in degrees F, and the Battery %

## Holley input can ids are as follows.
### For pressure
Configure as CAN 5V Sensors with a Type of Custom 5v, the voltage scale will be 0-5v, and the Pressure scale will be 0-50PSI.
Use the CAN IDs and input numbers from the list below.

*Can I/O Module ID 1575
** Input 1 = Driver Front
** Input 2 = Passenger Front
** Input 3 = Driver Rear
** Input 4 = Passenger Rear

### For Temperature
Configure as CAN 5v Sensors with a Type of Custom 5V, the voltage scale will be 0-5V and the temperature scale will be 0-212 F.
Use the CAN IDs and input numbers from the list below.
* Can ID 1575
** Input 5 = Driver Front
** Input 6 = Passenger Front
** Input 7 = Driver Rear
** Input 8 = Passenger Rear

### For Battery
Configure as CAN 5V Sensors with a Type of Custom 5V, the voltage scale will be 0-5V and the scale will be 0-100%.
Use the CAN IDs and input numbers from the list below.
* Can ID 1576
** Input 1 = Driver Front
** Input 2 = Passenger Front
** Input 3 = Driver Rear
** Input 4 = Passenger Rear

