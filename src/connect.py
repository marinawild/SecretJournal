import serial
import time

ser = serial.Serial("COM6", 115200, timeout=1)

time.sleep(2)
ser.reset_input_buffer()


print("Waiting for Arduino READY...")

while True:
    line = ser.readline().decode().strip()
    if line == "READY":
        print("Arduino connected!")
        break

while True:
    line = ser.readline().decode().strip()

    if not line:
        continue

    print("Arduino:", line)

    # Arduino requests verification
    if line == "VERIFY":
        print("Verification requested")

        # YOUR LOGIC HERE
        approved = True  # replace with real check

        if approved:
            ser.write(b"UNLOCK\n")
            print("Sent UNLOCK")
        else:
            print("Denied")
