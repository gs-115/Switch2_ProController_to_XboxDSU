import usb.util
import struct
import time
import multiprocessing
import vgamepad as vg
import json
import sys
import ctypes
import socket
from binascii import crc32
import math

# NS2PC_to_Xbox+DSU
# Script by gs_115 / Niro

# User Parameters, Edit them to your preferences

Use_C_As_Remap_Button = True  # When set to False, only pressing enter will begin the remap sequence
# In Combine, change state events will be sent by both the G button and the original
# In Boolean, the button will be pressed if the G button or the original button is pressed
GL_GR_Behavior = "Boolean"  # Combine / Boolean

# Off, capture button is unused
# Steam, presses the f12 button
# WindowsGB, (Windows Game Bar), short press to take a screenshot, hold to record last 30 sec (if enabled)
Capture_Button_Mode = "Steam"

Capture_SFX_Volume = 10  # 0 to 255, default 10, setting to 0 will only leave the low frequency rumble enabled
Auto_Continuous_Gyro_Calibration = True
Rumble_Intensity = 250  # 0 to 255
Simulate_Rumble_Speed_Up = 10  # Rumble will react slower with bigger values, set to 0 or 1 to disable effect, 60 emulates an xbox 360 controller
Large_Motor_Freq = 42.5  # Hz
Small_Motor_Freq = 100  # Hz
Fast_Comm = True  # The Xbox tasks won't sleep when the USB task has not yet sent a new message, increases CPU usage by 50%

Test_Rumble = 0  # 0 normal function, 1 pulse rumble, 2 test frequencies, 3 test amplitude
Print_Polling_Speed = False  # Print the time between updates of input states

# When tested on windows 10, usb pooling time is 4ms (250Hz),
# output polling time is 4+-0.2ms (250Hz) with Fast_Comm and 15+-10ms (60Hz) without
# On a rhythm game ADOFAI the input delay is between 30-45ms with Fast_Comm and 25-50ms without
# For reference my keyboard measured a latency of 15-25ms
# Delay could be the same, however Fast_Comm will be a lot more consistent in polling rate

# DSU Server Options
localIP = "127.0.0.1"
localPort = 26760
bufferSize = 1024


commands_steam = [  # Commands sent from steam input in usb mode
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\x00\x30\x01\x00",  # Spi reads
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\x40\x30\x01\x00",
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\x80\x30\x01\x00",
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\xc0\x30\x01\x00",
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\x00\x31\x01\x00",
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\x40\xc0\x1f\x00",
    b"\x02\x91\x00\x01\x00\x08\x00\x00\x00\x00\x00\x00\x80\xc0\x1f\x00",
    b"\x07\x91\x00\x01\x00\x00\x00\x00",  # 0x07
    b"\x0c\x91\x00\x02\x00\x04\x00\x00\x27\x00\x00\x00",  # Init features, buttons, sticks, Motion, current
    b"\x11\x91\x00\x01\x00\x00\x00\x00",  # 0x11
    b"\x0a\x91\x00\x08\x00\x14\x00\x00\x01\xff\xff\xff\xff\xff\xff\xff\xff\x35\x00\x46\x00\x00\x00\x00\x00\x00\x00\x00",  # Vibration
    b"\x0c\x91\x00\x04\x00\x04\x00\x00\x27\x00\x00\x00",  # Enable features, buttons, sticks, Motion, current
    b"\x01\x91\x00\x0c\x00\x00\x00\x00",  # MCU
    b"\x01\x91\x00\x01\x00\x00\x00\x00",  # MCU
    b"\x08\x91\x00\x02\x00\x04\x00\x00\x01\x00\x00\x00",  # 0x08
    b"\x03\x91\x00\x0a\x00\x04\x00\x00\x05\x00\x00\x00",  # Init
    b"\x03\x91\x00\x0d\x00\x08\x00\x00\x01\x00\xff\xff\xff\xff\xff\xff",  # Init
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00",  # LED 1000
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # LED 0000
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00",  # LED 1000
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # LED 0000
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # LED 0000
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # LED 0000
    b"\x09\x91\x00\x07\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # LED 0000
]

# Rumble/haptic data is read by the controller in LE order
# Order of hex values in the actual rumble buffer:
# MAIN PITCH [1-0],
# MAIN AMPLITUDE [0]-MAIN PITCH [2],
# SECONDARY PITCH[0]-MAIN AMPLITUDE [1],
# SECONDARY PITCH[2-1],
# SECONDARY AMPLITUDE[1-0]

# So if the data is written in the BE order
# SECONDARY AMPLITUDE[1-0]
# SECONDARY PITCH[2-1],
# SECONDARY PITCH[0]-MAIN AMPLITUDE [1],
# MAIN AMPLITUDE [0]-MAIN PITCH [2],
# MAIN PITCH [1-0]
# Meaning the rumble data can control the pitch (3 hex values = 1.5 bytes) and amplitude (1 bytes) of two signals for a total of (1+1.5)*2=5 bytes

# MAIN and SECONDARY are only names I used, the two signals don't seems to have any hierarchy or differences

# Amplitude between 0x00-0xFF (seems linear?)
# Frequency between 0x000-0x330 (not linear) to create a sound (the conversion function freq_to_byte was mapped using value from 60hz to 3700Hz)

# Frequency to hex: b = 96.4187235416 * log2( f / 10.7) with f in Herts ( b=0 if f <= 10.7)
# Hex to frequency: f = 10.7 * 2^( h / 96.4187235416 )

# The frequency range loops 4 times in the 0x000 to 0xFFF range since the last two MSB are unused
# It could be possible for example to use values in the 0x3FF to 0x7FF range to get sounds
# The frequency starts looping after reaching ~3720Hz
# The frequency behaves weirdly before reaching the 0x3ff mark and starting over normally

# Since there are still empty bytes in the rumble command buffer,
# it could be that more complex sounds can be sent, but I have not tested it

# Every rumble frame lasts ~12ms according to steam input
# If the frames are sent too fast, the controller will close the communication and will need to be plugged back in
# rumble_test = [
#     [0x3f, 0x01, 0xf5, 0x5f, 0x00],
#     [0x75, 0x21, 0x35, 0x5f, 0x00],
#     [0x75, 0x21, 0xb6, 0x5f, 0x00],
#     [0x75, 0x21, 0xf5, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
#     [0x75, 0x01, 0xb3, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
#     [0x75, 0x21, 0xb5, 0x5f, 0x00],
# ]

client_addr = 0
counter = -10

KSC_list = [" ",b"ESC","1234567890-=",b"BCSP",b"TAB","QWERTYUIOP[]",b"ENTER",b"CTRL","ASDFGHJKL;'‛",b"L_SHIFT",
            "\\ZXCVBNM,./",b"R_SHIFT",b"PRISC",b"ALT",b"SPACE",b"CAPS",b"F1",b"F2",b"F3",b"F4",b"F5",b"F6",b"F7",b"F8",b"F9",
            b"F10",b"NUM",b"SCROLL",b"HOME",b"UP",b"PGUP",b"GRAY-",b"LEFT",b"CENTER",b"RIGHT",b"GRAY+",b"END",b"DOWN",b"PGDN",b"INS",
            b"DEL","   ",b"F11",b"F12"]
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time",ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                 ("mi", MouseInput),
                 ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

def task_USB_COMM(button_link, motionaxis_link, haptic_link):
    buttons_code = {
        "A": 0x08000000,
        "B": 0x04000000,
        "X": 0x02000000,
        "Y": 0x01000000,
        "DPLeft": 0x00000800,
        "DPUp": 0x00000200,
        "DPRight": 0x00000400,
        "DPDown": 0x00000100,
        "L": 0x00004000,
        "R": 0x40000000,
        "ZL": 0x00008000,
        "ZR": 0x80000000,
        "StickLPress": 0x00080000,
        "StickRPress": 0x00040000,
        "Start": 0x00020000,
        "Select": 0x00010000,
        "Home": 0x00100000,
        "Capture": 0x00200000,
        "C": 0x00400000,
        "GL": 0x00000002,
        "GR": 0x00000001
    }

    def send_command(device, b, in_endpoint=0x02, out_endpoint=0x82, read_buffer_size=64):
        device.write(in_endpoint, bytes(b))
        time.sleep(0.001)
        resp = bytes(device.read(out_endpoint, read_buffer_size))
        return resp

    def send_led_command(device, led=0x00):  # (0, 0, 0, 0)
        if type(led) == list or type(led) == tuple:
            led = led[0]+2*led[1]+4*led[2]+8*led[3]
        com = (0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, led, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)
        return send_command(device, bytes(com))

    def decode_joystick(data):
        x = ((data[1] & 0x0F) << 8) | data[0]
        y = (data[2] << 4) | ((data[1] & 0xF0) >> 4)
        x = (x - 2048) / 2048.0
        y = (y - 2048) / 2048.0
        return max(-1.0, min(1.0, x * 1.2)), max(-1.0, min(1.0, y * 1.2))

    def translate_input(b):
        if len(b) >= 16:
            resp = {"valid": True}
            try:
                resp["PacketID"] = struct.unpack("<i", bytes(b[1:5]))[0]
                buttons = int.from_bytes(b[5:9], byteorder="big")
                # print(' '.join('{:02x}'.format(x) for x in b[5:9]))
                resp["Buttons"] = {}
                for button in buttons_code.keys():
                    resp["Buttons"][button] = (255 if (buttons & buttons_code[button]) else 0)
                resp["Buttons"]["LeftStick"] = decode_joystick(b[11:14])
                resp["Buttons"]["RightStick"] = decode_joystick(b[14:17])
                resp["MotionActive"] = True
                try:
                    m_b = b[43:]
                    resp["Motion"] = {}
                    m = resp["Motion"]
                    m["IMUSampleValue"] = struct.unpack("<I", m_b[0:4])[0]
                    m["Temp"] = 25+struct.unpack("<h", m_b[4:6])[0]/127
                    m["AccelX"], m["AccelY"], m["AccelZ"], m["GyroX"], m["GyroY"], m["GyroZ"] = struct.unpack("<hhhhhh", m_b[6:18])
                except Exception:
                    resp["MotionActive"] = False
                # print(' '.join('{:02x}'.format(x) for x in b[0:]))
                # print(resp["Motion"])
            except Exception:
                resp["valid"] = False
        else:
            resp = {"valid": False}
        return resp

    def create_rumble_buffer(main_A=0, main_f=0, second_A=0, second_f=0):
        # Amplitude between 0x00-0xFF
        # Frequency between 0x510-0x730 to create a sound
        # The frequency range seems to loop multiple times in the 0x000 to 0xFFF range
        return [second_f & 0x0FF,
                ((second_A & 0x0F) << 4) | ((second_f & 0xF00) >> 8),
                ((main_f & 0x00F) << 4) | ((second_A & 0xF0) >> 4),
                (main_f & 0xFF0) >> 4,
                main_A & 0xFF]

    def freq_to_byte(f):  # In Herts, range 0hz to 3700Hz
        if f <= 10.7:
            return 0
        return int(96.4187235416*math.log(f/10.7, 2)+0.5)

    def bytes_to_freq(b):
        return 10.7*2**(b/96.4187235416)

    # First approximation
    # def freq_to_byte_firstversion(f):  # In Herts, range 70hz to 3700Hz, function created from an experiment, results are only an approximate
    #     return int((-10.936868188*math.exp(-0.00185*f)+0.0012*f+19.28)*34.278271004+1024)

    def gen_sound(main_A=(0,0), main_f=(0,0), second_A=(0,0), second_f=(0,0), frames=1):
        buffer = []
        for fr_i in range(frames):
            c = fr_i/max(frames-1, 1)
            m_A, s_A = int(main_A[1]*c+main_A[0]*(1-c)), int(second_A[1]*c+second_A[0]*(1-c))
            m_f, s_f = freq_to_byte(main_f[1]*c+main_f[0]*(1-c)), freq_to_byte(second_f[1]*c+second_f[0]*(1-c))
            buffer.append(create_rumble_buffer(m_A,m_f,s_A,s_f))
        return buffer

    def gen_sound_sequence(rumble_desc):
        buffer = []
        for el in rumble_desc:
            sub_b = gen_sound(*el)
            for command in sub_b:
                buffer.append(command)
        return buffer

    screenshot_sfx = [
        ((20, 20), (250, 200), (0, 0), (50, 120), 2),
        ((Capture_SFX_Volume*0.2, Capture_SFX_Volume*0.2), (600, 650), (Capture_SFX_Volume*0.2, Capture_SFX_Volume*0.2), (500, 530), 2),
        ((Capture_SFX_Volume*0.5, Capture_SFX_Volume*0.1), (1900, 1920), (Capture_SFX_Volume*0.2, Capture_SFX_Volume*0.2), (3520, 3520), 4),
        ((Capture_SFX_Volume*0.1, Capture_SFX_Volume*0.0), (1920, 1950), (Capture_SFX_Volume*0.2, 0), (3520, 3520), 4),
        ((Capture_SFX_Volume * 0.8, Capture_SFX_Volume * 0.8), (2600, 2600), (Capture_SFX_Volume*0.1, 0), (2800, 2800), 5),
        ((Capture_SFX_Volume*0.8, Capture_SFX_Volume * 0.0), (2600, 2600), (0, 0), (2800, 2500), 5)
    ]
    vid_capture_sfx = [
        ((20, 20), (250, 200), (0, 0), (50, 120), 2),
        ((0, Capture_SFX_Volume),(1800, 1920),(0, Capture_SFX_Volume*0.01), (3520, 3520), 3),
        ((Capture_SFX_Volume, Capture_SFX_Volume*0.8),(1900, 1950),(Capture_SFX_Volume*0.01, Capture_SFX_Volume*0.0), (3520, 3520), 3),
        ((Capture_SFX_Volume*0.8, Capture_SFX_Volume*0.0),(1900, 1900),(0, 0), (3520, 3520), 5),
        ((0,0),(0,0),(0,0),(0,0),60),
        ((20, 20), (250, 200), (0, 0), (50, 120), 2),
        ((Capture_SFX_Volume, Capture_SFX_Volume*0.8),(2080, 2180),(0,0), (0,0), 5),
        ((Capture_SFX_Volume, Capture_SFX_Volume*0.8),(2800, 2800),(0,0), (0,0), 5),
        ((Capture_SFX_Volume*0.8, Capture_SFX_Volume*0),(2800, 2800),(0,0), (0,0), 5)
    ]
    screenshot_sfx = gen_sound_sequence(screenshot_sfx)
    vid_capture_sfx = gen_sound_sequence(vid_capture_sfx)

    play_sfx = [-1, []]

    print("[USB] USB Task Started")
    time.sleep(0.2)
    connected = False
    starting = True
    total_messages = -100
    try:
        while True:
            try:
                # Pro 2 controller connection
                motor = [0,0]
                motors = [[0]*max(Simulate_Rumble_Speed_Up, 1), [0]*max(Simulate_Rumble_Speed_Up, 1)]  # Large Motor, Small Motor
                dev = usb.core.find(idVendor=0x057E, idProduct=0x2069)
                for com in commands_steam:
                    send_command(dev, bytes(com))
                send_led_command(dev, 0x01)
                # print(dev)
                # print(dir(dev))

                print("[USB] Connected to Pro 2 Controller")
                connected = True
                starting = False
                read_c = 0
                read_every = 1
                rumble_count = 0
                start_ns = time.time_ns()
                last_rumble = 0
                test_count = 0
                motors_avr = [0, 0]

                total_time_messages = 0
                last_message = 0
                while True:
                    while haptic_link.poll():
                        n_motor = haptic_link.recv()
                        if n_motor[0] < 0:
                            if n_motor[0] == -1 and play_sfx[0] == -1:  # Screenshot SFX
                                play_sfx[0] = 0
                                play_sfx[1] = screenshot_sfx
                            elif n_motor[0] == -2 and play_sfx[0] == -1:  # Video Capture SFX
                                play_sfx[0] = 0
                                play_sfx[1] = vid_capture_sfx
                        else:
                            if Simulate_Rumble_Speed_Up > 1:
                                motor = n_motor
                            else:
                                motors_avr = haptic_link.recv()
                    current_time_ns = time.time_ns() - start_ns
                    upd_haptic = current_time_ns-last_rumble > 12000000  # 12 ms between commands
                    if upd_haptic and Simulate_Rumble_Speed_Up > 1:
                        motors[0].append(motor[0])
                        motors[0].pop(0)
                        motors[1].append(motor[1])
                        motors[1].pop(0)
                        motors_avr = [int(sum(motors[0])/len(motors[0])),int(sum(motors[1])/len(motors[1]))]
                    if (((time.time() % 2) < 1 and Test_Rumble == 1) or (motors_avr[0] > 0 or motors_avr[1] > 0) or Test_Rumble == 2 or Test_Rumble == 3 or play_sfx[0] >= 0) and upd_haptic:  # 12 ms between commands
                        rumble_m = [0x00] * 64
                        rumble_m[0] = 0x02
                        rumble_m[1] = 0x50 + (rumble_count & 0x0F)
                        rumble_m[17] = rumble_m[1]
                        if play_sfx[0] >= 0:
                            rumble_command = play_sfx[1][play_sfx[0]]
                            play_sfx[0] += 1
                            if play_sfx[0] >= len(play_sfx[1]):
                                play_sfx = [-1, []]
                        else:
                            if Test_Rumble == 0:
                                rumble_command = create_rumble_buffer(main_A=int(motors_avr[0]*Rumble_Intensity/255),
                                                                      main_f=freq_to_byte(motors_avr[0]*Large_Motor_Freq/255),
                                                                      second_A=int(motors_avr[1]*Rumble_Intensity*0.8/255),
                                                                      second_f=freq_to_byte(motors_avr[0]*Small_Motor_Freq/255))
                            elif Test_Rumble == 1:
                                rumble_command = [0x87, 0x89, 0x23, 0x91, 0x38]
                            elif Test_Rumble == 2:
                                rumble_command = create_rumble_buffer(main_A=0x10, main_f=((test_count//2) if test_count > 4 else 1024+500), second_A=0, second_f=0)
                                test_count = (test_count+1)%(0xFFF*2)
                                print("Testing Rumble Frequencies:", test_count//2,"/ 4095 points (4 1023 points long loops in the sequence)")
                            elif Test_Rumble == 3:
                                rumble_command = create_rumble_buffer(main_A=((test_count//3) if test_count > 8 else 80), main_f=200, second_A=0, second_f=0)
                                test_count = (test_count+1)%(0xFF*3)
                                print("Testing Rumble Amplitude:", test_count//3,"/ 256 points")
                        rumble_m[2:7] = rumble_command
                        rumble_m[18:23] = rumble_command
                        try:
                            dev.write(0x1, bytes(rumble_m))
                        except usb.core.USBTimeoutError:
                            ...
                        rumble_count = (rumble_count+1) & 0x0F
                        last_rumble = current_time_ns
                    b = bytes(dev.read(0x81, 128))
                    read_c = (read_c + 1)%read_every
                    if read_c == 0:
                        m = translate_input(b)
                        if m["valid"]:
                            if Print_Polling_Speed and total_messages < 350:
                                total_messages += 1
                                if total_messages == 350:
                                    print("[USB] Average time between messages",(total_time_messages/total_messages)/1e6, "ms")
                                elif total_messages > 0:
                                    total_time_messages += current_time_ns-last_message
                                last_message = current_time_ns
                            button_link.send(m["Buttons"])
                            if m["MotionActive"]:
                                motionaxis_link.send(m["Motion"])
            except (AttributeError, usb.core.USBError) as e:  # Controller not plugged in, Controller disconnected
                ...
            if connected:
                print("[USB] Controller Disconnected")
                connected = False
            if starting:
                print("[USB] Please plug in your Pro 2 Controller using a USB Cable")
                starting = False
            time.sleep(1)
    except KeyboardInterrupt:
        if connected:
            print("[USB] Turning off lights...")
            send_led_command(dev, 0x00)

def task_Xbox_Emul(button_link, comline_link, haptic_link):
    button_keys = {
        "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        "DPLeft": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "DPUp": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "DPRight": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        "DPDown": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "L": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "R": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        # "ZL"
        # "ZR"
        "StickLPress": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        "StickRPress": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        "Start": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
        "Select": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "Home": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        # "Capture"
        # "C"
        # "GL"
        # "GR"
    }
    default_abxy = {
        "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_X
    }

    def press_key(hexKeyCode, extended=False):
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | (0x0001 if extended else 0x0000), 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

    def release_key(hexKeyCode, extended=False):
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | 0x0002 | (0x0001 if extended else 0x0000), 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

    def KSC_to_Char(k):
        if k > 88:
            return "NONE"
        trg = "NONE"
        s = 0
        while k > 0:
            s += 1
            if type(KSC_list[s]) == bytes:
                trg = KSC_list[s].decode("utf-8")
                k -= 1
            else:
                for chara in KSC_list[s]:
                    k -= 1
                    if k == 0:
                        trg = chara
                        break
        return trg
    
    def stick_display(mi, v, ma, resolution=29):
        mi = max(min(mi, 1), -1)
        v = max(min(v, 1), -1)
        ma = max(min(ma, 1), -1)
        t = ["-"]*resolution
        for i in range(int((mi+1.0)*(resolution-1)/2), int((ma+1.0)*(resolution-1)/2)+1):
            t[i] = "▓"
        t[int((mi+1.0)*(resolution-1)/2)] = "["
        t[int((ma+1.0)*(resolution-1)/2)] = "]"
        t[int((resolution-1)/2)] = "+"
        t[int((v+1.0)*(resolution-1)/2)] = "|"
        return "".join(t)

    def transform_stick_cal(v, cal_data):
        # 0min, 1center, 2max
        if v < cal_data[1]:
            return max((v-cal_data[1])/(cal_data[1]-cal_data[0]), -1.0)
        else:
            return min((v-cal_data[1])/(cal_data[2]-cal_data[1]), 1.0)

    def apply_deadzone(x, y, d):
        if x**2+y**2<d**2:
            return 0.0, 0.0
        return x, y

    def translate_saved_map(sm):
        return "GL: "+sm["GL"]+", GR: "+sm["GR"]

    def save_mapping():
        file = open("NS2PC_to_Xbox+DSU.json", "w+")
        json.dump(saved_mapping, file)
        file.close()
        print("[X/U] Saved config. ", translate_saved_map(saved_mapping), ", Special GL: " + KSC_to_Char(saved_mapping["GL_KEYBOARD"]) + " , Special GR: " + KSC_to_Char(saved_mapping["GR_KEYBOARD"]))

    def vibration_register(client, target, large_motor, small_motor, led_number, user_data):
        # Motor value 0 to 255
        haptic_link.send((large_motor, small_motor))

    gp = vg.VX360Gamepad()
    gp.register_notification(callback_function=vibration_register)
    buttons = {}
    special_state = {"Capture": False, "C": False, "GL": False, "GR": False}
    special_buttons = tuple(special_state.keys())
    normal_buttons = tuple(button_keys.keys())
    print("[X/U] Xbox/User Task Started")
    try:
        file = open("NS2PC_to_Xbox+DSU.json", "r")
        saved_mapping = json.load(file)
        file.close()
        print("[X/U] Reloaded saved config:", translate_saved_map(saved_mapping),
              ", Special GL: " + KSC_to_Char(saved_mapping["GL_KEYBOARD"]) +
              " , Special GR: " + KSC_to_Char(saved_mapping["GR_KEYBOARD"]))
    except FileNotFoundError:
        print("[X/U] Loaded default parameters, please calibrate joysticks using 'cal' before playing")
        saved_mapping = {"GL": "", "GR": "", "LX": [-1,0,1], "LY": [-1,0,1], "RX": [-1,0,1], "RY": [-1,0,1], "DeadZoneL": 0.05, "DeadZoneR": 0.05, "GL_KEYBOARD": 17, "GR_KEYBOARD": 45}
    print("[X/U] Press enter "+("(or C) " if Use_C_As_Remap_Button else "")+'to remap the GL/GR buttons. Type "cal" to calibrate the sticks, "swap" to swap the A/B and X/Y buttons')
    remap_logic = {"Phase": 0, "GL|GR": "", "RequestRemap": False}
    calibration_logic = {"Phase": 0, "Data": [0, 0, 0, 0]}
    boolean_b_logic = {"Real": {"GL": False, "GR": False}, "Back": {"GL": False, "GR": False}}
    capture_btn_press_time = 0
    total_messages = -1
    total_time_messages = 0
    total_process_time = 0
    last_message = time.time_ns()
    try:
        while True:
            new_com = False
            w_time = 0
            while (not button_link.poll()) and w_time < 100 and not Fast_Comm:
                time.sleep(0.001)  # on windows more likely ~13ms
                w_time += 1
            while button_link.poll() and not Fast_Comm:
                buttons_n = button_link.recv()
                new_com = True
            if Fast_Comm:
                buttons_n = button_link.recv()
                while button_link.poll():
                    buttons_n = button_link.recv()
                new_com = True
            if Print_Polling_Speed and total_messages <= 450:
                input_recv_time = time.time_ns()
            if comline_link.poll():
                co = comline_link.recv()
                if co == "cal" and remap_logic["Phase"] == 0 and calibration_logic["Phase"] == 0:
                    calibration_logic["Phase"] = 1
                    print("1--- Calibrating Left Stick ---")
                    print("Move the left stick in a circle slowly to set the minimum/maximum of the axis. A to save. B to skip.")
                    joysticks = [0, 0, 0, 0]
                elif co == "swap":
                    if default_abxy["A"] == button_keys["A"]:
                        button_keys["A"] = default_abxy["B"]
                        button_keys["B"] = default_abxy["A"]
                        button_keys["X"] = default_abxy["Y"]
                        button_keys["Y"] = default_abxy["X"]
                        print("[X/U] Swapped A/B and X/Y buttons.")
                    else:
                        button_keys["A"] = default_abxy["A"]
                        button_keys["B"] = default_abxy["B"]
                        button_keys["X"] = default_abxy["X"]
                        button_keys["Y"] = default_abxy["Y"]
                        print("[X/U] Reapplied correct A/B and X/Y button positions.")
                elif co == "" and remap_logic["Phase"] < 2 and calibration_logic["Phase"] == 0:
                    remap_logic["RequestRemap"] = True
            special_delta = {"Capture": 0, "C": 0, "GL": 0, "GR": 0}
            pressed_button = []
            register_pressed_button = (remap_logic["Phase"] == 2 or remap_logic["Phase"] == 3 or calibration_logic["Phase"] > 0)
            updated_boolean = False
            if new_com:
                for b in buttons_n.keys():
                    if b not in ("LeftStick", "RightStick") and ((b not in buttons) or buttons_n[b] != buttons[b]):
                        if b in button_keys:
                            if GL_GR_Behavior == "Boolean" and b == saved_mapping["GL"] or b == saved_mapping["GR"]:
                                for back_button in ("GL", "GR"):
                                    if b == saved_mapping[back_button]:
                                        boolean_b_logic["Real"][back_button] = buttons_n[b]
                                        updated_boolean = True
                                if buttons_n[b] and register_pressed_button:
                                    pressed_button.append(b)
                            else:
                                if buttons_n[b]:
                                    gp.press_button(button_keys[b])
                                    if register_pressed_button:
                                        pressed_button.append(b)
                                else:
                                    gp.release_button(button_keys[b])
                        elif b == "ZL":
                            if GL_GR_Behavior == "Boolean" and b == saved_mapping["GL"] or b == saved_mapping["GR"]:
                                for back_button in ("GL", "GR"):
                                    if b == saved_mapping[back_button]:
                                        boolean_b_logic["Real"][back_button] = buttons_n[b]
                                        updated_boolean = True
                            else:
                                gp.left_trigger(buttons_n[b])
                            if register_pressed_button and buttons_n[b]:
                                pressed_button.append(b)
                        elif b == "ZR":
                            if GL_GR_Behavior == "Boolean" and b == saved_mapping["GL"] or b == saved_mapping["GR"]:
                                for back_button in ("GL", "GR"):
                                    if b == saved_mapping[back_button]:
                                        boolean_b_logic["Real"][back_button] = buttons_n[b]
                                        updated_boolean = True
                            else:
                                gp.right_trigger(buttons_n[b])
                            if register_pressed_button and buttons_n[b]:
                                pressed_button.append(b)
                        elif b in special_buttons:
                            if b not in buttons:
                                special_delta[b] = buttons_n[b]
                                special_state[b] = buttons_n[b]
                            elif buttons_n[b] != buttons[b]:
                                special_delta[b] = buttons_n[b]-buttons[b]
                                special_state[b] = buttons_n[b]
                            if remap_logic["Phase"] == 0 and (b == "GL" or b == "GR"):
                                if saved_mapping[b] == "SPECIAL_KEYBOARD":
                                    if buttons_n[b]:
                                        press_key(saved_mapping[b+"_KEYBOARD"])
                                    else:
                                        release_key(saved_mapping[b+"_KEYBOARD"])
                                else:
                                    if GL_GR_Behavior == "Boolean":
                                        if saved_mapping[b] != "":
                                            updated_boolean = True
                                            boolean_b_logic["Back"][b] = buttons_n[saved_mapping[b]]
                                    else:
                                        if saved_mapping[b] in normal_buttons:
                                            if buttons_n[b]:
                                                gp.press_button(button_keys[saved_mapping[b]])
                                            else:
                                                gp.release_button(button_keys[saved_mapping[b]])
                                        elif saved_mapping[b] == "ZL":
                                            gp.left_trigger(buttons_n[b])
                                        elif saved_mapping[b] == "ZR":
                                            gp.right_trigger(buttons_n[b])
                    elif b == "LeftStick":
                        s_x, s_y = apply_deadzone(transform_stick_cal(buttons_n[b][0], saved_mapping["LX"]), transform_stick_cal(buttons_n[b][1], saved_mapping["LY"]), saved_mapping["DeadZoneL"])
                        gp.left_joystick_float(x_value_float=s_x, y_value_float=s_y)
                    elif b == "RightStick":
                        s_x, s_y = apply_deadzone(transform_stick_cal(buttons_n[b][0], saved_mapping["RX"]), transform_stick_cal(buttons_n[b][1], saved_mapping["RY"]), saved_mapping["DeadZoneR"])
                        gp.right_joystick_float(x_value_float=s_x, y_value_float=s_y)
                if updated_boolean:
                    if saved_mapping["GL"] == saved_mapping["GR"] and saved_mapping["GL"] not in ("", "SPECIAL_KEYBOARD"):
                        press_real_button = (bool(buttons_n["GL"] or buttons_n["GR"] or buttons_n[saved_mapping["GL"]]) and remap_logic["Phase"] == 0)
                        if saved_mapping["GL"] == "ZL":
                            gp.left_trigger(press_real_button*255)
                        elif saved_mapping["GL"] == "ZR":
                            gp.right_trigger(press_real_button*255)
                        else:
                            if press_real_button:
                                gp.press_button(button_keys[saved_mapping["GL"]])
                            else:
                                gp.release_button(button_keys[saved_mapping["GL"]])
                    else:
                        for back_button in ("GL", "GR"):
                            if saved_mapping[back_button] not in ("", "SPECIAL_KEYBOARD"):
                                press_real_button = (buttons_n[back_button] or buttons_n[saved_mapping[back_button]]) and remap_logic["Phase"] == 0
                                if saved_mapping[back_button] == "ZL":
                                    gp.left_trigger(press_real_button*255)
                                elif saved_mapping[back_button] == "ZR":
                                    gp.right_trigger(press_real_button*255)
                                else:
                                    if press_real_button:
                                        gp.press_button(button_keys[saved_mapping[back_button]])
                                    else:
                                        gp.release_button(button_keys[saved_mapping[back_button]])
                if calibration_logic["Phase"] == 4:
                    if -0.4 < buttons_n["LeftStick"][0] < 0.4 and abs(calibration_logic["Data"][2]) >= 1:
                        calibration_logic["Data"][2] = 0
                    elif abs(buttons_n["LeftStick"][0]) > 0.6 and calibration_logic["Data"][2] == 0:
                        calibration_logic["Data"][2] = -1 if buttons_n["LeftStick"][0] < 0 else 1
                    if -0.4 < buttons_n["RightStick"][0] < 0.4 and abs(calibration_logic["Data"][3]) >= 1:
                        calibration_logic["Data"][3] = 0
                    elif abs(buttons_n["RightStick"][0]) > 0.6 and calibration_logic["Data"][3] == 0:
                        calibration_logic["Data"][3] = -1 if buttons_n["RightStick"][0] < 0 else 1
                gp.update()
                buttons = buttons_n
                if Print_Polling_Speed and total_messages < 450:
                    total_messages += 1
                    if total_messages == 450:
                        print("[X/U] Average time between updates", (total_time_messages / (total_messages-300)) / 1e6, "ms")
                        print("[X/U] Average input process time", (total_process_time / (total_messages-300)) / 1e6, "ms")
                    elif total_messages > 300:
                        total_time_messages += time.time_ns()-last_message
                        total_process_time += time.time_ns()-input_recv_time
                    last_message = time.time_ns()
            if Capture_Button_Mode == "Steam":
                if special_delta["Capture"] == 255:
                    press_key(0x58)  # F12 Scan Code
                    haptic_link.send((-1, -1))  # Screenshot Rumble SFX
                elif special_delta["Capture"] == -255:
                    release_key(0x58)  # F12 Scan Code
            elif Capture_Button_Mode == "WindowsGB":
                if special_delta["Capture"] == 255:
                    capture_btn_press_time = time.time()
                elif special_delta["Capture"] == -255:
                    if time.time() - capture_btn_press_time < 0.5:
                        # Take screenshot
                        press_key(0xE05B, extended=True)  # Windows Key Scan Code
                        press_key(0x38)  # Alt Key Scan Code
                        press_key(0x54)  # PrtScr Key Scan Code
                        haptic_link.send((-1, -1))  # Screenshot Rumble SFX
                        time.sleep(0.05)
                        release_key(0x54)
                        release_key(0x38)
                        release_key(0xE05B, extended=True)
                    capture_btn_press_time = 0
                if capture_btn_press_time > 0 and time.time() - capture_btn_press_time >= 0.5:
                    # Record last 30 sec
                    press_key(0xE05B, extended=True)  # Windows Key Scan Code
                    press_key(0x38)  # Alt Key Scan Code
                    press_key(0x22)  # G Key Scan Code
                    haptic_link.send((-2, -2))  # Video Record Rumble SFX
                    time.sleep(0.05)
                    release_key(0x22)
                    release_key(0x38)
                    release_key(0xE05B, extended=True)
                    capture_btn_press_time = 0


            if Use_C_As_Remap_Button and special_delta["C"] == 255:
                remap_logic["RequestRemap"] = True
            if remap_logic["Phase"] > 0:
                if remap_logic["Phase"] == 4:
                    for i in range(255):
                        if abs(ctypes.windll.user32.GetKeyState(i)) > 100 and KSC_to_Char(ctypes.windll.user32.MapVirtualKeyA(i, 0)) not in [" ", "NONE"]:
                            tr = ctypes.windll.user32.MapVirtualKeyA(i, 0)
                            saved_mapping[remap_logic["GL|GR"]+"_KEYBOARD"] = tr
                            print("[X/U] Set "+remap_logic["GL|GR"]+"'s special key to '"+KSC_to_Char(tr)+"'.")
                            remap_logic = {"Phase": 0, "GL|GR": "", "RequestRemap": False}
                            save_mapping()
                elif remap_logic["Phase"] == 3:
                    for b in pressed_button:
                        if buttons[b]:
                            if b == "A":
                                remap_logic["Phase"] = 4
                                print("[X/U]* Press a key on your keyboard to save it. Scanning... *")
                            else:
                                print("[X/U] Did not update key.")
                                remap_logic = {"Phase": 0, "GL|GR": "", "RequestRemap": False}
                                save_mapping()
                elif remap_logic["Phase"] == 2:
                    p_b = ""
                    for b in pressed_button:
                        if buttons[b]:
                            p_b = b
                            break
                    if GL_GR_Behavior == "Boolean" and saved_mapping[remap_logic["GL|GR"]] not in ("", "SPECIAL_KEYBOARD") and (p_b != "" or special_delta["GL"] == 255 or special_delta["GR"] == 255 or special_delta["C"] == 255):
                        if not boolean_b_logic["Real"][remap_logic["GL|GR"]]:
                            if saved_mapping[remap_logic["GL|GR"]] == "ZL":
                                gp.left_trigger(0)
                            elif saved_mapping[remap_logic["GL|GR"]] == "ZR":
                                gp.right_trigger(0)
                            else:
                                gp.release_button(button_keys[saved_mapping[remap_logic["GL|GR"]]])
                    if p_b != "":
                        saved_mapping[remap_logic["GL|GR"]] = p_b
                        print("[X/U] Mapped " + remap_logic["GL|GR"] + " to " + saved_mapping[remap_logic["GL|GR"]] + ".")
                        remap_logic = {"Phase": 0, "GL|GR": "", "RequestRemap": False}
                        save_mapping()
                    elif special_delta["GL"] == 255 or special_delta["GR"] == 255:
                        saved_mapping[remap_logic["GL|GR"]] = ""
                        print("[X/U] Cleared mapping for "+remap_logic["GL|GR"]+".")
                        remap_logic = {"Phase": 0, "GL|GR": "", "RequestRemap": False}
                        save_mapping()
                    elif special_delta["C"] == 255:
                        remap_logic["Phase"] = 3
                        saved_mapping[remap_logic["GL|GR"]] = "SPECIAL_KEYBOARD"
                        print("[X/U]* " + remap_logic["GL|GR"] + "'s special key is mapped to the key '" + KSC_to_Char(saved_mapping[remap_logic["GL|GR"] + "_KEYBOARD"]) + "'. Would you like to change this key? A yes / B no *")
                elif remap_logic["Phase"] == 1 and not remap_logic["RequestRemap"]:
                    if special_delta["GL"] == 255:
                        remap_logic["GL|GR"] = "GL"
                    elif special_delta["GR"] == 255:
                        remap_logic["GL|GR"] = "GR"
                    if remap_logic["GL|GR"] != "":
                        print("[X/U]* Selected remap for "+remap_logic["GL|GR"]+". Press the button to remap to, press C to map to special keyboard key, or press GL/GR to clear mapping *")
                        remap_logic["Phase"] = 2
            if remap_logic["RequestRemap"]:
                if remap_logic["Phase"] == 0:
                    print("[X/U]* Press the button you want to remap (GL/GR). Press Enter to cancel" + (" (or C)" if Use_C_As_Remap_Button else "")+" *")
                    remap_logic["Phase"] = 1
                elif remap_logic["Phase"] == 1:
                    print("[X/U] Canceled Remap")
                    remap_logic = {"Phase": 0, "GL|GR": "", "RequestRemap": False}

            if calibration_logic["Phase"] > 0:
                if calibration_logic["Phase"] == 1:  # Left stick min-max
                    print(" Left Stick X: " + stick_display(calibration_logic["Data"][0], joysticks[0], calibration_logic["Data"][1]) + " Y: " + stick_display(calibration_logic["Data"][2], joysticks[1], calibration_logic["Data"][3]), end="\r", flush=True)
                    if "A" in pressed_button or "B" in pressed_button:
                        print(" ")
                        if "A" in pressed_button:
                            saved_mapping["LX"][0] = calibration_logic["Data"][0]
                            saved_mapping["LX"][2] = calibration_logic["Data"][1]
                            saved_mapping["LY"][0] = calibration_logic["Data"][2]
                            saved_mapping["LY"][2] = calibration_logic["Data"][3]
                        else:
                            print("Skipped")
                        calibration_logic["Phase"] += 1
                        calibration_logic["Data"] = [0, 0, 0, 0]
                        print("2--- Calibrating Right Stick ---")
                        print("Move the right stick in a circle slowly to set the minimum/maximum of the axis. A to save. B to skip.")
                    calibration_logic["Data"][0] = min(calibration_logic["Data"][0], buttons["LeftStick"][0])
                    calibration_logic["Data"][1] = max(calibration_logic["Data"][1], buttons["LeftStick"][0])
                    calibration_logic["Data"][2] = min(calibration_logic["Data"][2], buttons["LeftStick"][1])
                    calibration_logic["Data"][3] = max(calibration_logic["Data"][3], buttons["LeftStick"][1])
                elif calibration_logic["Phase"] == 2:  # Right stick min-max
                    print(" Right Stick X: " + stick_display(calibration_logic["Data"][0], joysticks[2], calibration_logic["Data"][1]) + " Y: " + stick_display(calibration_logic["Data"][2], joysticks[3], calibration_logic["Data"][3]), end="\r", flush=True)
                    if "A" in pressed_button or "B" in pressed_button:
                        print(" ")
                        if "A" in pressed_button:
                            saved_mapping["RX"][0] = calibration_logic["Data"][0]
                            saved_mapping["RX"][2] = calibration_logic["Data"][1]
                            saved_mapping["RY"][0] = calibration_logic["Data"][2]
                            saved_mapping["RY"][2] = calibration_logic["Data"][3]
                        else:
                            print("Skipped")
                        calibration_logic["Phase"] += 1
                        calibration_logic["Data"] = [0, 0, 0, 0]
                        print("3--- Calibrating Stick centers ---")
                        print("Let go the sticks and then press A. A to save. B to skip.")
                    calibration_logic["Data"][0] = min(calibration_logic["Data"][0], buttons["RightStick"][0])
                    calibration_logic["Data"][1] = max(calibration_logic["Data"][1], buttons["RightStick"][0])
                    calibration_logic["Data"][2] = min(calibration_logic["Data"][2], buttons["RightStick"][1])
                    calibration_logic["Data"][3] = max(calibration_logic["Data"][3], buttons["RightStick"][1])
                elif calibration_logic["Phase"] == 3:  # Sticks center
                    if "A" in pressed_button or "B" in pressed_button:
                        if "A" in pressed_button:
                            saved_mapping["LX"][1] = buttons["LeftStick"][0]
                            saved_mapping["LY"][1] = buttons["LeftStick"][1]
                            saved_mapping["RX"][1] = buttons["RightStick"][0]
                            saved_mapping["RY"][1] = buttons["RightStick"][1]
                        else:
                            print("Skipped")
                        calibration_logic["Phase"] = 4
                        calibration_logic["Data"] = [int(saved_mapping["DeadZoneL"]*1000), int(saved_mapping["DeadZoneR"]*1000), 0, 0]
                        print("4--- Dead Zones ---")
                        print("Move sticks left or right to change their respective deadzone.")
                elif calibration_logic["Phase"] == 4:  # DeadZones
                    if abs(calibration_logic["Data"][2]) == 1:
                        calibration_logic["Data"][0] = max(calibration_logic["Data"][0]+calibration_logic["Data"][2], 0)
                        calibration_logic["Data"][2] = 2
                    elif abs(calibration_logic["Data"][3]) == 1:
                        calibration_logic["Data"][1] = max(calibration_logic["Data"][1]+calibration_logic["Data"][3], 0)
                        calibration_logic["Data"][3] = 2
                    print(" Left Stick: "+str(calibration_logic["Data"][0]/10)+"% Right Stick: "+str(calibration_logic["Data"][1]/10)+"%", end="\r", flush=True)
                    if "A" in pressed_button or "B" in pressed_button:
                        print(" ")
                        if "A" in pressed_button:
                            saved_mapping["DeadZoneL"] = calibration_logic["Data"][0]/1000
                            saved_mapping["DeadZoneR"] = calibration_logic["Data"][1]/1000
                        else:
                            print("Skipped")
                        calibration_logic["Phase"] = 0
                        calibration_logic["Data"] = [0, 0, 0, 0]
                        print("--- Calibration Finished ---")
                        file = open("NS2PC_to_Xbox+DSU.json", "w+")
                        json.dump(saved_mapping, file)
                        file.close()
                        print("[X/U] Saved calibration. ")

            remap_logic["RequestRemap"] = False
    except KeyboardInterrupt:
        ...

def task_DSU_Gyro_Server(gyro_link):
    global client_addr
    UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    UDPServerSocket.bind((localIP, localPort))

    def gen_message(msg_type, data=[0], device_active=True, device_id=0):
        # controller_id, active, has_gyro, connection_type, Mac addr (6), battery status
        if device_active:
            data = (device_id, 2, 2, 0, 0xC6, 0x78, 0x54, 0x12, 0x63, 0x48, 0x05)+tuple(data)
        else:
            data = (device_id, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0)+tuple(data)
        ms = [0x44, 0x53, 0x55, 0x53, # DSU
              0xE9, 0x03,  # Version
              *struct.pack('<H', len(data) + 4), # packet Len
              0x00, 0x00, 0x00, 0x00,  # CRC32
              0xff, 0xff, 0xff, 0xff,  # server ID
              *tuple(Msg_types[msg_type]),
              *data]
        crc = crc32(bytes(ms)) & 0xFFFFFFFF
        ms[8:12] = struct.pack('<I', crc)
        return bytes(ms)

    Msg_types = {"Version": b"\x00\x00\x10\x00", "Ports": b"\x01\x00\x10\x00", "Data": b"\x02\x00\x10\x00"}

    def ports(message, address):
        requests_count = struct.unpack("<I", message[20:24])[0]
        for slot_id in message[24: 24+requests_count]:
            if slot_id == 0:
                UDPServerSocket.sendto(gen_message("Ports"), address)
            else:
                UDPServerSocket.sendto(gen_message("Ports", device_active=False, device_id=slot_id), address)

    def new_request_(request):
        global client_addr
        b, addr = request
        if len(b) >= 19:
            msg_type = b[16:20]
            if msg_type == Msg_types["Version"]: # Version
                ...
            elif msg_type == Msg_types["Ports"]: # Ports
                ports(b, addr)
            elif msg_type == Msg_types["Data"]: # Data
                if client_addr != addr:
                    print("[DSU] DSU Client Detected:", addr)
                    client_addr = addr

    def send_gyro(address, gyro_data, cal):
        global counter

        sensors = [
            -gyro_data["AccelX"]/4096,
            -gyro_data["AccelZ"]/4096,
            gyro_data["AccelY"]/4096,
        ]
        sensors.extend([
            (gyro_data["GyroX"]-cal[0])*(360/48000)*7.9,
            -(gyro_data["GyroZ"]-cal[2])*(360/48000)*7.9,
            (gyro_data["GyroY"]-cal[1])*(360/48000)*7.9,
        ])
        IMUFrames_per_second_avrg = 1000000  # measured 996000
        # time.time_ns() // 1000
        timestamp = int((gyro_data["IMUSampleValue"]/IMUFrames_per_second_avrg)*1e6) # ms
        data = [
            0x01,  # is active (true)
            *struct.pack('<I', max(counter, 0)),
            0x00,
            0x00,
            0x00,  # PS
            0x00,  # Touch
            128,  # position left x
            128,  # position left y
            128,  # position right x
            128,  # position right y
            0x00,  # dpad left 0-255
            0x00,  # dpad down
            0x00,  # dpad right
            0x00,  # dpad up
            0x00,  # square
            0x00,  # cross
            0x00,  # circle
            0x00,  # triange
            0x00,  # r1
            0x00,  # l1
            0x00,  # r2
            0x00,  # l2
            0x00,  # track pad first is active (false)
            0x00,  # track pad first id
            0x00, 0x00,  # trackpad first x
            0x00, 0x00,  # trackpad first y
            0x00,  # track pad second is active (false)
            0x00,  # track pad second id
            0x00, 0x00,  # trackpad second x
            0x00, 0x00,  # trackpad second y
            *struct.pack('<Q', timestamp),  # Motion data timestamp
            *struct.pack('<ffffff', *sensors)  # Accelerometer and Gyroscope data
        ]
        counter += 1

        if counter >= 0:
            UDPServerSocket.sendto(gen_message("Data", data=data), address)

    print("[DSU] DSU Server Task Started")
    gyro = {}
    cal = [0, 0, 0]
    UDPServerSocket.settimeout(0.005)
    last_time = time.time()

    # Gyro Calibration logic
    avrg_cal = [0, 0, 0]
    avrg_total_time = 0
    last_val = (0, 0, 0)
    max_der = 260  # °/s^2
    still_duration = 3  # s
    try:
        while True:
            dt = time.time() - last_time
            last_time = time.time()
            while not gyro_link.poll():
                try:
                    new_request_(UDPServerSocket.recvfrom(bufferSize))
                except (socket.timeout, ConnectionResetError):
                    ...
            while gyro_link.poll():
                gyro = gyro_link.recv()
                val = (gyro["GyroX"], gyro["GyroY"], gyro["GyroZ"])
                if 0 < dt < 0.2:
                    val_der = [(last_val[i]-val[i])/dt for i in range(3)]
                    valid = True
                    for i in range(3):
                        if abs(val_der[i]) > max_der:
                            valid = False
                            break
                    if valid:
                        for i in range(3):
                            avrg_cal[i] += (val[i]+last_val[i])*dt/2
                        avrg_total_time += dt
                        if avrg_total_time > still_duration:
                            if cal[0] == 0 and cal[1] == 0 and cal[2] == 0:
                                print(f"[DSU] Calibrated Gyro")
                                cal = [avrg_cal[0]/avrg_total_time, avrg_cal[1]/avrg_total_time, avrg_cal[2]/avrg_total_time]
                            else:
                                cal = [avrg_cal[0]/avrg_total_time, avrg_cal[1]/avrg_total_time, avrg_cal[2]/avrg_total_time]
                            avrg_cal = [0, 0, 0]
                            avrg_total_time = 0
                    else:
                        avrg_cal = [0, 0, 0]
                        avrg_total_time = 0
                last_val = val
            if "IMUSampleValue" in gyro:
                if client_addr != 0:
                    send_gyro(client_addr, gyro, cal)
    except KeyboardInterrupt:
        ...

def task_com_line_input(link):
    sys.stdin = open(0)
    try:
        while True:
            t = input()
            link.send(t)
    except KeyboardInterrupt:
        ...


if __name__ == '__main__':
    l_button, l_button_ = multiprocessing.Pipe(duplex=False)
    l_gyro, l_gyro_ = multiprocessing.Pipe(duplex=False)
    l_comline, l_comline_ = multiprocessing.Pipe(duplex=False)
    l_haptic, l_haptic_ = multiprocessing.Pipe(duplex=False)

    try:
        t_usb = multiprocessing.Process(target=task_USB_COMM, args=(l_button_, l_gyro_, l_haptic))
        t_usb.start()
        t_button = multiprocessing.Process(target=task_Xbox_Emul, args=(l_button, l_comline, l_haptic_))
        t_button.start()
        t_comline = multiprocessing.Process(target=task_com_line_input, args=(l_comline_, ))
        t_comline.start()
        t_dsugyro = multiprocessing.Process(target=task_DSU_Gyro_Server, args=(l_gyro, ))
        t_dsugyro.start()
        t_usb.join()
        t_button.join()
        t_comline.join()
        t_dsugyro.join()
    except KeyboardInterrupt:
        ...

