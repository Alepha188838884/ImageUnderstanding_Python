import queue
import threading
import time
from typing import Callable, Dict

try:
    import RPi.GPIO as GPIO
except ImportError:  # 允许在非树莓派环境下导入
    GPIO = None


class ASRGPIOTrigger:
    """按 BCM + PUD_UP 规范轮询 GPIO，检测低电平下降沿触发动作。"""

    def __init__(
        self,
        pin_action_map: Dict[int, str],
        handler: Callable[[str], None],
        *,
        pull_up: bool = True,
        bouncetime_ms: int = 250,
        min_interval: float = 0.3,
        poll_interval: float = 0.02,
        debug_poll: bool = False,
        debug_poll_every: float = 0.2,
    ):
        if GPIO is None:
            raise ImportError("未找到 GPIO 库，请在树莓派5安装 rpi-lgpio（RPi.GPIO 兼容层）")
        if not pin_action_map:
            raise ValueError("pin_action_map 不能为空")
        if not pull_up:
            raise ValueError("按 bcm24_test.py 规范，GPIO 输入必须使用 GPIO.PUD_UP（触发时拉低）")
        self._pin_action_map = dict(pin_action_map)
        self._handler = handler
        self._bouncetime_ms = max(0, int(bouncetime_ms))
        self._min_interval = max(0.0, float(min_interval))
        self._poll_interval = max(0.001, float(poll_interval))
        self._debug_poll = bool(debug_poll)
        self._debug_poll_every = max(0.02, float(debug_poll_every))
        self._last_debug_print = 0.0
        self._trigger_interval = max(self._min_interval, self._bouncetime_ms / 1000.0)
        self._last_trigger = {pin: 0.0 for pin in self._pin_action_map}
        self._pin_state = {pin: 1 for pin in self._pin_action_map}
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._poller = threading.Thread(target=self._poll_loop, daemon=True)
        self._started = False

    def start(self):
        if self._started:
            return
        GPIO.setmode(GPIO.BCM)
        worker_started = False
        poller_started = False
        try:
            for pin in self._pin_action_map:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                self._pin_state[pin] = GPIO.input(pin)
            if self._debug_poll:
                state_text = ", ".join(
                    f"BCM{pin}={self._pin_state[pin]}" for pin in sorted(self._pin_state)
                )
                print(f"[GPIO初始电平] {state_text}")
            self._worker.start()
            worker_started = True
            self._poller.start()
            poller_started = True
            self._started = True
        except Exception:
            self._stop.set()
            if poller_started and self._poller.is_alive():
                self._poller.join(timeout=1.0)
            if worker_started and self._worker.is_alive():
                self._worker.join(timeout=1.0)
            GPIO.cleanup()
            raise

    def close(self):
        if not self._started:
            return
        self._stop.set()
        if self._poller.is_alive():
            self._poller.join(timeout=1.0)
        if self._worker.is_alive():
            self._worker.join(timeout=1.0)
        GPIO.cleanup()
        self._started = False

    def _poll_loop(self):
        while not self._stop.is_set():
            poll_state_text = []
            for pin, action_word in self._pin_action_map.items():
                try:
                    state = GPIO.input(pin)
                except Exception as exc:
                    print(f"GPIO 读取失败（BCM{pin}）: {exc}")
                    continue
                if self._debug_poll:
                    poll_state_text.append(f"BCM{pin}={state}")

                previous = self._pin_state.get(pin, 1)
                self._pin_state[pin] = state

                # 上升沿空闲、下降沿触发（PUD_UP 下 0 表示触发）
                if previous == 1 and state == 0:
                    now = time.monotonic()
                    last_time = self._last_trigger.get(pin, 0.0)
                    if (now - last_time) >= self._trigger_interval:
                        self._last_trigger[pin] = now
                        print(f"[GPIO触发检测] BCM{pin} -> {action_word}")
                        self._queue.put(action_word)

            if self._debug_poll:
                now = time.monotonic()
                if (now - self._last_debug_print) >= self._debug_poll_every:
                    print(f"[GPIO轮询] {' '.join(poll_state_text)}")
                    self._last_debug_print = now

            time.sleep(self._poll_interval)

    def _worker_loop(self):
        while not self._stop.is_set():
            try:
                action_word = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._handler(action_word)
            except Exception as exc:
                print(f"GPIO 触发执行失败: {exc}")
            finally:
                self._queue.task_done()
