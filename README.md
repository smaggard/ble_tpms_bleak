# ble_tpms_bleak
TPMS system that will send messages to a Holley Terminator X or Dominator as a Can I/O module

# Installation
## Install required modules.
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
TODO
