import usb.core
import usb.util
import struct
import time

VENDOR_ID = 0xEBA4
PRODUCT_ID = 0x1303

# UVC constants
REQ_SET_CUR = 0x01
REQ_GET_CUR = 0x81
BM_REQ_SET = 0x21   # Host->Device | Class | Interface
BM_REQ_GET = 0xA1   # Device->Host | Class | Interface

# Control Selectors (Camera Terminal)
UVC_CT_FOCUS_AUTO_CONTROL      = 0x08
UVC_CT_FOCUS_ABSOLUTE_CONTROL  = 0x06

def find_device():
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        raise RuntimeError("没找到设备（检查是否插好或ID是否正确）")
    dev.set_configuration()
    return dev

def parse_camera_terminal_entity_id(dev):
    """
    在 VideoControl 接口的 extra_descriptors 里找到 Camera Terminal (wTerminalType=0x0201) 的 bTerminalID
    返回 (interface_number, camera_terminal_id)
    """
    for cfg in dev:
        for intf in cfg:
            if intf.bInterfaceClass == 14 and intf.bInterfaceSubClass == 1:  # CC_VIDEO=14, SC_VIDEOCONTROL=1
                data = bytes(intf.extra_descriptors)
                # 逐段解析 CS_INTERFACE 描述符
                i = 0
                while i + 2 <= len(data):
                    # 所有 USB 描述符都以长度、类型开头
                    bLength = data[i]
                    if bLength == 0 or i + bLength > len(data):
                        break
                    bDescriptorType = data[i+1]
                    # CS_INTERFACE = 0x24
                    if bDescriptorType == 0x24 and bLength >= 3:
                        bDescriptorSubType = data[i+2]
                        # INPUT_TERMINAL = 0x02
                        if bDescriptorSubType == 0x02 and bLength >= 8:
                            # 布局（UVC 1.1/1.5 简化）：bLength, bDescriptorType, bDescriptorSubType, bTerminalID, wTerminalType(2), bAssocTerminal, iTerminal ...
                            bTerminalID = data[i+3]
                            wTerminalType = struct.unpack_from("<H", data, i+4)[0]
                            if wTerminalType == 0x0201:  # ITT_CAMERA
                                return (intf.bInterfaceNumber, bTerminalID)
                    i += bLength
    raise RuntimeError("没有解析到 Camera Terminal（可能是非标固件，或设备以其他方式暴露）")

def set_focus_auto(dev, intf, entity_id, on=True):
    # wValue: (CS << 8) | channel(0)
    wValue = (UVC_CT_FOCUS_AUTO_CONTROL << 8) | 0
    # wIndex: (entity_id << 8) | interface_number
    wIndex = (entity_id << 8) | intf
    data = bytes([1 if on else 0])
    dev.ctrl_transfer(BM_REQ_SET, REQ_SET_CUR, wValue, wIndex, data, timeout=1000)

def set_focus_absolute(dev, intf, entity_id, value):
    """
    value: 16-bit 小端，有的设备范围是 0~255，有的更大；先试 0~255。
    """
    if value < 0 or value > 65535:
        raise ValueError("焦距超范围")
    wValue = (UVC_CT_FOCUS_ABSOLUTE_CONTROL << 8) | 0
    wIndex = (entity_id << 8) | intf
    data = struct.pack("<H", value)  # little-endian
    dev.ctrl_transfer(BM_REQ_SET, REQ_SET_CUR, wValue, wIndex, data, timeout=1000)

def get_focus_auto(dev, intf, entity_id):
    wValue = (UVC_CT_FOCUS_AUTO_CONTROL << 8) | 0
    wIndex = (entity_id << 8) | intf
    resp = dev.ctrl_transfer(BM_REQ_GET, REQ_GET_CUR, wValue, wIndex, 1, timeout=1000)
    return int(resp[0])

def get_focus_absolute(dev, intf, entity_id):
    wValue = (UVC_CT_FOCUS_ABSOLUTE_CONTROL << 8) | 0
    wIndex = (entity_id << 8) | intf
    resp = dev.ctrl_transfer(BM_REQ_GET, REQ_GET_CUR, wValue, wIndex, 2, timeout=1000)
    return struct.unpack("<H", resp.tobytes())[0]

if __name__ == "__main__":
    dev = find_device()
    prod = usb.util.get_string(dev, dev.iProduct) or "UVC Camera"
    print(f"✅ 设备：{prod}")
    intf, cam_id = parse_camera_terminal_entity_id(dev)
    print(f"🔎 VideoControl 接口号: {intf}  | Camera Terminal ID: {cam_id}")

    # 先读一眼当前状态（有些固件只允许 GET，不允许 SET；读成功说明路径对了）
    try:
        af = get_focus_auto(dev, intf, cam_id)
        print(f"ℹ️ 当前自动对焦: {af}")
    except usb.core.USBError as e:
        print("⚠️ 读取自动对焦状态失败（但不一定致命）：", e)

    # 尝试开启自动对焦
    try:
        set_focus_auto(dev, intf, cam_id, True)
        time.sleep(0.5)
        print("📸 已尝试开启自动对焦（看画面是否‘呼吸’一下）")
    except usb.core.USBError as e:
        print("❌ 开启自动对焦失败：", e)

    # 如果你想手动定焦（示例：100）
    # try:
    #     set_focus_auto(dev, intf, cam_id, False)
    #     set_focus_absolute(dev, intf, cam_id, 100)
    #     print("🎯 已切换到手动并设置焦距=100（可按需改数值重试）")
    # except usb.core.USBError as e:
    #     print("❌ 手动对焦设置失败：", e)
