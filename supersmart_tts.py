# -*- coding:utf-8 -*-

import _thread as thread
import base64
import hashlib
import hmac
import json
import os
import shutil
import ssl
import subprocess
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import websocket

import config


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_MP3 = "answer.mp3"
DEFAULT_TTS_URL = "wss://tts-api.xfyun.cn/v2/tts"
DEFAULT_VCN = "x4_yezi"
DEFAULT_TTE = "utf8"
DEFAULT_AUE = "lame"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_SPEED = 50
DEFAULT_VOLUME = 50
DEFAULT_PITCH = 50

# TTS service config
TTS_APP_ID = config.XFYUN_APP_ID
TTS_API_KEY = config.XFYUN_API_KEY
TTS_API_SECRET = config.XFYUN_API_SECRET
TTS_URL = DEFAULT_TTS_URL
TTS_VCN = DEFAULT_VCN
TTS_TTE = DEFAULT_TTE
TTS_AUE = DEFAULT_AUE
TTS_SAMPLE_RATE = DEFAULT_SAMPLE_RATE
TTS_SPEED = DEFAULT_SPEED
TTS_VOLUME = DEFAULT_VOLUME
TTS_PITCH = DEFAULT_PITCH

# Audio output config: set AUDIO_DEVICE to ALSA device like "hw:1,0" or "plughw:1,0"
AUDIO_DEVICE = ""
PLAY_SPEED = 1.2


def _run_command(cmd):
    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode == 0
    except Exception:
        return False


def _play_audio(audio_path):
    if not os.path.exists(audio_path):
        raise RuntimeError(f"待播放音频不存在: {audio_path}")

    candidates = []
    if shutil.which("mpg123"):
        if AUDIO_DEVICE:
            candidates.append(["mpg123", "-q", "-a", AUDIO_DEVICE, audio_path])
        else:
            candidates.append(["mpg123", "-q", audio_path])
    if shutil.which("ffplay"):
        candidates.append(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", audio_path])
    if shutil.which("cvlc"):
        candidates.append(["cvlc", "--intf", "dummy", "--play-and-exit", audio_path])
    if shutil.which("play"):
        candidates.append(["play", "-q", audio_path, "speed", str(PLAY_SPEED)])

    for cmd in candidates:
        print("播放命令:", " ".join(cmd))
        if _run_command(cmd):
            return

    raise RuntimeError(
        "找不到可用的终端音频播放器，请安装 mpg123（推荐）或 ffplay/cvlc/sox。"
    )


def _resolve_output_path():
    return os.path.join(PROJECT_DIR, OUTPUT_MP3)


def _load_tts_config():
    return {
        "app_id": TTS_APP_ID.strip(),
        "api_key": TTS_API_KEY.strip(),
        "api_secret": TTS_API_SECRET.strip(),
        "url": (TTS_URL or DEFAULT_TTS_URL).strip(),
        "vcn": (TTS_VCN or DEFAULT_VCN).strip(),
        "tte": (TTS_TTE or DEFAULT_TTE).strip(),
        "aue": (TTS_AUE or DEFAULT_AUE).strip(),
        "sample_rate": max(8000, min(24000, int(TTS_SAMPLE_RATE))),
        "speed": max(0, min(100, int(TTS_SPEED))),
        "volume": max(0, min(100, int(TTS_VOLUME))),
        "pitch": max(0, min(100, int(TTS_PITCH))),
    }


def _validate_tts_config(config):
    missing = []
    if not config["app_id"]:
        missing.append("TTS_APP_ID")
    if not config["api_key"]:
        missing.append("TTS_API_KEY")
    if not config["api_secret"]:
        missing.append("TTS_API_SECRET")
    if missing:
        print(
            "[TTS] 缺少讯飞 TTS 配置，请在 supersmart_tts.py 顶部填写："
            + ", ".join(missing)
        )
        return False
    return True


class WsParam:
    def __init__(self, app_id, api_key, api_secret, text, config):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.text = text
        self.tts_url = config["url"]
        self.common_args = {"app_id": self.app_id}
        self.business_args = {
            "aue": config["aue"],
            "auf": f"audio/L16;rate={config['sample_rate']}",
            "vcn": config["vcn"],
            "tte": config["tte"],
            "speed": config["speed"],
            "volume": config["volume"],
            "pitch": config["pitch"],
        }
        self.data = {
            "status": 2,
            "text": base64.b64encode(self.text.encode("utf-8")).decode("utf-8"),
        }

    def create_url(self):
        parsed = urlparse(self.tts_url)
        host = parsed.netloc
        path = parsed.path or "/"
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode("utf-8")

        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature_sha}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        return self.tts_url + "?" + urlencode(
            {
                "authorization": authorization,
                "date": date,
                "host": host,
            }
        )


def func(text):
    text = (text or "").strip()
    if not text:
        print("[TTS] 输入文本为空，跳过语音合成。")
        return False

    config = _load_tts_config()
    if not _validate_tts_config(config):
        return False

    output_file = _resolve_output_path()
    if os.path.exists(output_file):
        os.remove(output_file)

    state = {
        "code": 0,
        "message": "",
        "sid": "",
        "ws_error": "",
    }

    ws_param = WsParam(
        app_id=config["app_id"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        text=text,
        config=config,
    )

    def on_message(ws, message):
        try:
            payload = json.loads(message)
            code = int(payload.get("code", 0))
            sid = payload.get("sid", "")
            if code != 0:
                state["code"] = code
                state["sid"] = str(sid)
                state["message"] = str(payload.get("message", ""))
                print(
                    f"[TTS] 服务返回错误: code={code}, sid={sid}, message={state['message']}"
                )
                ws.close()
                return

            data = payload.get("data", {})
            audio_b64 = data.get("audio")
            status = int(data.get("status", 0))
            if audio_b64:
                audio = base64.b64decode(audio_b64)
                with open(output_file, "ab") as f:
                    f.write(audio)
            if status == 2:
                ws.close()
        except Exception as exc:
            state["ws_error"] = str(exc)
            print(f"[TTS] 解析服务响应失败: {exc}")
            ws.close()

    def on_error(ws, error):
        state["ws_error"] = str(error)
        print(f"[TTS] WebSocket错误: {error}")

    def on_close(ws, *args):
        return None

    def on_open(ws):
        def run(*args):
            request = json.dumps(
                {
                    "common": ws_param.common_args,
                    "business": ws_param.business_args,
                    "data": ws_param.data,
                }
            )
            print("------>开始发送文本数据")
            ws.send(request)

        thread.start_new_thread(run, ())

    if hasattr(websocket, "enableTrace"):
        websocket.enableTrace(False)

    ws = websocket.WebSocketApp(
        ws_param.create_url(),
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    if state["code"] != 0:
        return False
    if state["ws_error"] and (not os.path.exists(output_file) or os.path.getsize(output_file) == 0):
        print(f"[TTS] WebSocket异常，且未生成有效音频: {state['ws_error']}")
        return False
    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        print("[TTS] 未生成有效音频文件。")
        return False

    try:
        _play_audio(output_file)
    except Exception as exc:
        print(f"[TTS] 播放失败: {exc}")
        return False
    return True
