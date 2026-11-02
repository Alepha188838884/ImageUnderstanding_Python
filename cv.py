import cv2
import numpy as np
from pathlib import Path
import os
import time
import errno


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[CV {ts}] {msg}")


def _apply_gamma(image, gamma: float):
    if gamma <= 0:
        return image
    table = (np.linspace(0, 1, 256) ** gamma * 255).astype("uint8")
    return cv2.LUT(image, table)


def enhance_contrast(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    enhanced = _apply_gamma(enhanced, 1.2)
    hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
    h_channel, s_channel, v_channel = cv2.split(hsv)
    s_channel = np.clip(s_channel.astype(np.float32) * 1.25, 0, 255).astype(np.uint8)
    hsv = cv2.merge((h_channel, s_channel, v_channel))
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def capture_frame(cam_index: int = 0, enhance: bool = True, output_path: str = "snapshot.jpg") -> str:
    cam_index = 0
    _log(f"开始采集: cam_index={cam_index}, enhance={enhance}, cwd={os.getcwd()}")
    print("开始拍照")
    cap = cv2.VideoCapture(0, 0)
    print("结束拍照")
    if not cap.isOpened():
        raise OSError(errno.ENODEV, os.strerror(errno.ENODEV))
    try:
        ret, frame = cap.read()
        _log(f"读帧结果: ret={ret}")
    finally:
        cap.release()
        _log("摄像头已释放")
    if not ret:
        raise OSError(errno.EIO, os.strerror(errno.EIO))
    if frame is not None:
        _log(f"帧尺寸: {frame.shape[1]}x{frame.shape[0]}, 通道={frame.shape[2] if len(frame.shape) > 2 else 1}")
    if enhance:
        frame = enhance_contrast(frame)
        _log("已完成图像增强")
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    _log(f"准备写入文件: {output.resolve()}")
    ok = cv2.imwrite(str(output), frame)
    if not ok:
        raise OSError(errno.EIO, os.strerror(errno.EIO))
    saved = str(output.resolve())
    _log(f"保存成功: {saved}")
    return saved
