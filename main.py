import threading
import os
import time
import ImageUnderstanding
import cv
from asr_listener import ASRListener

try:
    from asr_pro_uart import ASRProUART
except ImportError:
    ASRProUART = None
try:
    from asr_gpio_listener import ASRGPIOTrigger
except ImportError:
    ASRGPIOTrigger = None

# 如果有自己的 ASR 识别函数，填到这里，比如 lambda prompt: my_asr.listen_once()
CUSTOM_ASR_FUNC = None
ASR_DEVICE = None

USE_ASR_PRO = True
ASR_PRO_PORT = "/dev/serial0"
ASR_PRO_BAUDRATE = 115200
ASR_PRO_HANDLES_WAKE = True
ASR_COMMAND_MAP = {
    "open": "看红绿灯",
    "light": "看红绿灯",
    "traffic": "看红绿灯",
    "blind": "看盲道",
    "path": "看盲道",
    "menu": "看菜单",
    "around": "看周围",
    "surround": "看周围",
}

WAKE_WORD = getattr(ImageUnderstanding, "WAKE_WORD", "智能助手")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_PATH = os.path.join(PROJECT_DIR, "snapshot.jpg")

USE_ASR_GPIO = True
ASR_GPIO_BOUNCETIME_MS = 250
ASR_GPIO_MIN_INTERVAL = 0.3
ASR_GPIO_POLL_INTERVAL = 0.02
ASR_GPIO_DEBUG_POLL = False
ASR_GPIO_DEBUG_POLL_EVERY = 0.2
ASR_GPIO_PIN_ACTION_MAP = {
    24: "看红绿灯",  # ID=1 -> PB5 -> BCM24
    25: "看盲道",    # ID=2 -> PB6 -> BCM25
    12: "看菜单",    # ID=3 -> PA2 -> BCM12
    16: "看周围",    # ID=4 -> PA3 -> BCM16
}
GPIO_LISTENER = None

ACTION_LOCK = threading.Lock()

if USE_ASR_PRO and ASRProUART:
    try:
        ASR_DEVICE = ASRProUART(port=ASR_PRO_PORT, baudrate=ASR_PRO_BAUDRATE)
        CUSTOM_ASR_FUNC = ASR_DEVICE.listen_once
        if ASR_PRO_HANDLES_WAKE:
            WAKE_WORD = ""
    except Exception as exc:
        print(f"ASR-PRO 初始化失败，回退到默认输入: {exc}")
        ASR_DEVICE = None
        CUSTOM_ASR_FUNC = None


def capture_and_process(action_word: str):
    with ACTION_LOCK:
        snapshot_path = cv.capture_frame(0, output_path=SNAPSHOT_PATH)
        ImageUnderstanding.main_program(snapshot_path, action_word)


def _handle_gpio_action(action_word: str):
    print(f"[GPIO触发] {action_word}")
    capture_and_process(action_word)


def _setup_gpio_listener():
    global GPIO_LISTENER
    if not USE_ASR_GPIO or not ASRGPIOTrigger:
        return
    try:
        GPIO_LISTENER = ASRGPIOTrigger(
            ASR_GPIO_PIN_ACTION_MAP,
            _handle_gpio_action,
            bouncetime_ms=ASR_GPIO_BOUNCETIME_MS,
            min_interval=ASR_GPIO_MIN_INTERVAL,
            poll_interval=ASR_GPIO_POLL_INTERVAL,
            debug_poll=ASR_GPIO_DEBUG_POLL,
            debug_poll_every=ASR_GPIO_DEBUG_POLL_EVERY,
        )
        GPIO_LISTENER.start()
        print("ASR GPIO 触发已启用（BCM + PUD_UP，轮询低电平触发）。")
    except Exception as exc:
        print(f"ASR GPIO 初始化失败，继续使用语音输入: {exc}")
        GPIO_LISTENER = None


def normalize_command_text(command_text: str) -> str:
    text = (command_text or "").strip()
    lowered = text.lower()
    if lowered in ASR_COMMAND_MAP:
        return ASR_COMMAND_MAP[lowered]
    if text in ASR_COMMAND_MAP:
        return ASR_COMMAND_MAP[text]
    return text


def main():
    listener = ASRListener(wake_word=WAKE_WORD, listen_func=CUSTOM_ASR_FUNC)
    command_prompt = "" if not WAKE_WORD else "请说出需要执行的功能："
    wake_tip = WAKE_WORD if WAKE_WORD else "（由ASR模块内置）"
    print(f"语音助手已启动，唤醒词：{wake_tip}")
    print(f"功能词汇：{'、'.join(ImageUnderstanding.activation_word)}")
    pin_mapping_text = '，'.join(
        f"BCM{pin}->{word}" for pin, word in ASR_GPIO_PIN_ACTION_MAP.items()
    )
    print(f"GPIO 功能映射：{pin_mapping_text}")
    _setup_gpio_listener()
    try:
        while True:
            if WAKE_WORD:
                listener.wait_for_wake_word()
                print("已唤醒，请说出需要执行的功能（说“退出”结束）。")
            while True:
                command_text = listener.listen_for_command(prompt_text=command_prompt)
                command_text = normalize_command_text(command_text)
                if not command_text:
                    # 已唤醒后不刷“未听到”，保持安静等待当前轮有效指令
                    time.sleep(0.05)
                    continue
                if "退出" in command_text:
                    print("收到退出指令，程序结束。")
                    return
                action_word = ImageUnderstanding.match_activation_command(command_text)
                if not action_word:
                    print(f"未识别到预设功能，支持：{'、'.join(ImageUnderstanding.activation_word)}")
                    continue
                capture_and_process(action_word)
                break
    finally:
        if ASR_DEVICE:
            ASR_DEVICE.close()
        if GPIO_LISTENER:
            GPIO_LISTENER.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出。")
