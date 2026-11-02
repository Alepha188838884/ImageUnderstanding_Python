# Voice-Controlled Vision Assistant for Blind Users

A Raspberry Pi prototype that lets a blind user ask, by voice, what is in front of them. A spoken command triggers a camera capture, a cloud vision model interprets the photo, and the answer is read aloud in Chinese.

**中文简介：** 这是一个面向视障人士的树莓派语音辅助设备原型。用户说出指令后，设备用摄像头拍照，交给云端图像理解模型分析，再把结果用语音播报出来。支持看红绿灯、看盲道、读文字和描述周围环境。

## What it does

| Voice command | Purpose | What the model is asked to do |
|---|---|---|
| 看红绿灯 (traffic light) | Crossing a road | Identify the light's colour and countdown, and guess the crossing's length. On green with a countdown, estimate whether there is time to cross. On green with no countdown, the prompt tells the model to say there is enough time |
| 看盲道 (tactile path) | Walking along a tactile path | Locate the path, check whether it is continuous or blocked, and suggest a way around obstacles |
| 看文本 / 看菜单 (read text) | Reading | Extract book text from the image line by line, keeping the layout |
| 看周围 (surroundings) | Orientation | Describe main objects, their rough positions, and anything relevant to moving safely |

Before each of these, the device first asks the model whether the camera lens looks dirty or blocked. Any answer is spoken, and the command then continues.

## How it works

```mermaid
flowchart LR
    A[Spoken command] --> B[ASR-PRO offline<br/>speech module]
    B -- GPIO pulse --> C[Raspberry Pi 5]
    C --> D[USB camera capture<br/>and image enhancement]
    D --> E[iFLYTEK Spark<br/>image understanding]
    E --> F[iFLYTEK TTS]
    F --> G[Speaker]
```

1. **Speech recognition.** An ASR-PRO module recognises the wake word (智能助手) and the commands on the device itself. Each command pulses its own output pin low for 200 ms.
2. **Trigger.** A background thread on the Pi polls the GPIO pins, detects the falling edge, and ignores repeat triggers on a pin within 0.3 s. A second thread runs the requested action, and a lock ensures only one capture and request runs at a time.
3. **Capture.** `cv.py` takes a frame and processes it: CLAHE contrast enhancement on the L channel, gamma correction, and a saturation boost.
4. **Understanding.** `ImageUnderstanding.py` sends the image and the matching prompt to the iFLYTEK Spark image API over a signed WebSocket connection.
5. **Speech output.** `supersmart_tts.py` turns the answer into an MP3 with iFLYTEK TTS and plays it with the first available player (`mpg123`, `ffplay`, `cvlc` or `play`).

## Hardware

- Raspberry Pi 5
- ASR-PRO speech recognition module
- USB (UVC) camera
- Speaker

### Wiring

| Command | ASR-PRO ID | ASR-PRO pin | Pi pin (BCM) | Action name in code |
|---|---|---|---|---|
| 看红绿灯 | 1 | PB5 | 24 | `看红绿灯` |
| 看盲道 | 2 | PB6 | 25 | `看盲道` |
| 看文本 | 3 | PA2 | 12 | `看菜单` |
| 看周围 | 4 | PA3 | 16 | `看周围` |

The Pi reads these pins with internal pull-ups, so a low level means "triggered". The word programmed on the module for ID 3 is 看文本, while the code calls the same action 看菜单. On the GPIO path this makes no difference, because the pin number selects the action. Typed or serial input must use 看菜单, since 看文本 is not recognised there.

### ASR-PRO program

The module is programmed with block code. It is included here as images rather than source files: [the command list and pin setup](2.jpg), and [the output pulse for each command](1.jpg).

## Running it

Requires Python 3 and an internet connection.

```bash
# System audio player
sudo apt install mpg123

# Python dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install opencv-python numpy websocket-client

# On the Raspberry Pi only
pip install pyserial rpi-lgpio

# API keys: copy the template, then fill in your own
cp config.example.py config.py

python main.py
```

`config.py` is excluded from git. `main.py` needs the iFLYTEK values (`XFYUN_*`), which also need the Spark image understanding and TTS services enabled on the account. `DASHSCOPE_API_KEY` is only used by `qwenVLMax.py`.

**Without the speech hardware**, for example on a laptop, the serial port cannot be opened and the program falls back to other input. On a Pi, set `USE_ASR_PRO = False` in `main.py` to get the same fallback. If `SpeechRecognition` is installed with PyAudio and a microphone, it uses Google's online recogniser. Otherwise it uses the keyboard: type 智能助手, then a command such as 看红绿灯 or 看菜单, or 退出 to quit. A camera and valid API keys are still needed.

## Project layout

| File | Purpose |
|---|---|
| `main.py` | Entry point: input handling, command matching, capture and answer flow |
| `ImageUnderstanding.py` | Prompts, KMP command matching, Spark image API client |
| `supersmart_tts.py` | iFLYTEK TTS client and audio playback |
| `cv.py` | Camera capture and image enhancement |
| `asr_gpio_listener.py` | GPIO polling, debouncing and worker thread |
| `asr_pro_uart.py` | Optional serial input, opened by default if the port exists. The block program shown here signals over GPIO |
| `asr_listener.py` | Wake word and command listener, with fallbacks |
| `bcm12_test.py`, `bcm24_test.py` | Hardware checks for individual GPIO pins |
| `camera_test.py` | Reads and sets camera autofocus over USB (UVC). Needs `pyusb` |
| `qwenVLMax.py` | Standalone experiment with Alibaba's Qwen VL model. Needs `openai` and your own test image |
| `keyboardinput.py` | Early keyboard input experiment, not used by `main.py` |
| `tts_ws_python3_demo/` | iFLYTEK's sample TTS code, kept for reference |
| `config.example.py` | Template for `config.py` |
| `demo.mp3` | Sample audio file, not used by the code |
| `1.jpg`, `2.jpg` | Images of the ASR-PRO block program |

## Limitations

- **Not a safety device.** This is a prototype. The model can be wrong, and its answers should not be relied on alone to cross a road. In particular, on a green light with no countdown it is told to report enough time without any estimate.
- **Needs a network.** Image understanding and speech output both use cloud services, so only the ASR-PRO's speech recognition works offline.
- **Slower per command.** Each command makes two model requests and can make two speech requests, because of the lens check.
- **TLS verification is off.** The WebSocket clients use `ssl.CERT_NONE`, which should be fixed before any real deployment.
- **No automated tests.** The test scripts here are manual hardware checks, and the test photos are not in this repository.
