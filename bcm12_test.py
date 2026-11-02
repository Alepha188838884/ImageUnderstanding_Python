import time

try:
    import RPi.GPIO as GPIO
except ImportError as exc:
    raise SystemExit(
        "RPi.GPIO is not available. Install the Raspberry Pi GPIO compatibility layer first."
    ) from exc


PIN = 12  # BCM 12
POLL_INTERVAL = 0.05
HEARTBEAT_INTERVAL = 1.0


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    last_state = GPIO.input(PIN)
    last_heartbeat = 0.0

    print("Start reading BCM12 (Ctrl+C to exit)")
    print("Mode: BCM")
    print("Input: PUD_UP")
    print("Trigger assumption: active low (falling edge 1 -> 0)")
    print(f"Initial BCM12 state: {last_state}")

    try:
        while True:
            now = time.monotonic()
            state = GPIO.input(PIN)

            if state != last_state:
                if last_state == 1 and state == 0:
                    edge = "falling edge"
                elif last_state == 0 and state == 1:
                    edge = "rising edge"
                else:
                    edge = "state change"

                print(f"BCM12 state changed: {last_state} -> {state} ({edge})")
                last_state = state

            if (now - last_heartbeat) >= HEARTBEAT_INTERVAL:
                print(f"BCM12 current state: {state}")
                last_heartbeat = now

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("Exit")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
