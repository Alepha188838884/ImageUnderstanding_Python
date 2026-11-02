import serial


class ASRProUART:
    def __init__(self, port: str = "/dev/serial0", baudrate: int = 115200, timeout: float = 0.5):
        self.serial = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.serial.reset_input_buffer()

    def listen_once(self, prompt_text: str = "") -> str:
        if prompt_text:
            print(prompt_text)
        data = self.serial.readline()
        if not data:
            return ""
        return data.decode("utf-8", errors="ignore").strip()

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
