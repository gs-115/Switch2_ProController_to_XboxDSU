# Switch2ProController_to_XboxDSU
Python script meant to communicate with a Nintendo Switch 2 Pro Controller through USB to translate the inputs into an Xbox controller and a DSU gyro server ("Cemuhook")

## Features
- All main buttons can be registered with an Xbox controller interface to increase compatibility
- GL and GR buttons can be remapped to all main buttons as well as keyboard keys
- The capture button works with Steam (Screenshot) and Windows game bar shortcuts (Screenshot with a short press + record last 30 sec with a long press)
- Gyro support through a DSU server ("Cemuhook")
- Rumble support
- 250Hz polling rate with <50ms of delay

## Limitations
- Wired communication only
- The script works on Windows only
- Only works with one Nintendo Switch 2 Pro Controller at a time
- HD Rumble can only be used by games using the Xbox interface, meaning only low rumble effects can be felt in-game
- Some features like the magnetometer or the NFC reader are unused

# How to install
The python scripts needs these 3 modules to function:
pyusb `pip install pyusb`
libusb `pip install libusb`
vgamepad `pip install vgamepad`, running this command will also prompt the install of the ViGEmBus driver, you can skip it if you already have it installed

Install the libusb backend:
[lisbusb website](https://libusb.info/)
Personally I had to install `libusb-1.0.29.7z` from the [libsub releases](https://github.com/libusb/libusb/releases) and then place `MinGW64\dll\libusb-1.0.dll` in `C:\Windows\System32\`

Set the user parameters of the script to your preferences (They are at the beginning)

Plug in your Pro 2 Controller, start the script, and type `cal` to calibrate the joysticks for the first time

# How to use
Press enter (or the C button on the controller if the option is still enabled) to change the mapping of the GL and GR buttons

Type `swap` to exchange the A/B and X/Y buttons

Most Nintendo emulators should recognize the Xbox interface and DSU server ("Cemuhook"), you only need to configure the inputs for rumble and gyro to work properly

# Resources used to create this script
Wireshark dissectors by german77, [JoyconDriver](https://github.com/german77/JoyconDriver)

Similar BLE scripts by TheFrano, [joycon2py](https://github.com/TheFrano/joycon2py) and [joycon2cpp](https://github.com/TheFrano/joycon2cpp)

Rumble formula inspiration, [Nintendo_Switch_Reverse_Engineering](https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering/tree/master)

Listening to Steam Input USB communication usign Wireshark
