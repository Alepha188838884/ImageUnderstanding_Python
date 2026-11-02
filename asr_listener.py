import time
from typing import Callable, Optional

try:
    import speech_recognition as sr  # 可选依赖：如果未安装则退回到键盘输入
except ImportError:
    sr = None


def _speech_recognition_listen(prompt_text: str = "") -> str:
    """使用 speech_recognition 录音并转文字，失败时返回空字符串。"""
    if not sr:
        return ""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        if prompt_text:
            print(prompt_text)
        audio = recognizer.listen(source, phrase_time_limit=6)
    try:
        return recognizer.recognize_google(audio, language="zh-CN")
    except Exception as exc:
        print(f"语音识别失败，改用键盘输入。原因: {exc}")
        return ""


def default_listen(prompt_text: str = "") -> str:
    """
    默认的捕获方法：优先用 speech_recognition，失败则退回到键盘输入。
    把你自己的 ASR 模块函数传给 ASRListener(listen_func=...) 就能替换掉这里的实现。
    """
    text = _speech_recognition_listen(prompt_text)
    if text:
        return text
    try:
        return input(prompt_text or ">>> ")
    except EOFError:
        return ""


class ASRListener:
    """
    基础的常开式监听器。
    listen_func 需要是一个返回识别文本的函数（无参数或只接收 prompt_text）。
    """

    def __init__(self, wake_word: str = "智能助手", listen_func: Optional[Callable[[str], str]] = None):
        self.wake_word = wake_word
        self.listen_func = listen_func or default_listen

    def listen_once(self, prompt_text: str = "") -> str:
        text = self.listen_func(prompt_text)
        if text is None:
            return ""
        cleaned = str(text).strip()
        if cleaned:
            print(f"[识别到] {cleaned}")
        return cleaned

    def wait_for_wake_word(self) -> str:
        """持续监听直到听到唤醒词，返回包含唤醒词的文本。"""
        while True:
            heard = self.listen_once(f"请说唤醒词（{self.wake_word}）：")
            if not heard:
                time.sleep(0.1)
                continue
            if self.wake_word in heard:
                return heard

    def listen_for_command(self, prompt_text: str = "请说出需要执行的功能：") -> str:
        """唤醒后再听一次命令文本。"""
        return self.listen_once(prompt_text)
