import RPi.GPIO as GPIO
import time

PIN = 24  # BCM 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
# 如果你的 ASR 输出是“触发时拉低”，用 PUD_UP 是最常见的

print("Start reading BCM24 (Ctrl+C to exit)")

try:
    while True:
        state = GPIO.input(PIN)
        print(f"BCM24 state: {state}")  # 1 = 高电平, 0 = 低电平
        time.sleep(0.2)
except KeyboardInterrupt:
    print("Exit")
finally:
    GPIO.cleanup()