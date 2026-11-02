from pynput import keyboard

def keyboard_press():
    last_key = None

    def on_press(key):
        global last_key
        try:
            last_key = key.char
        except AttributeError:
            last_key = str(key)

        if last_key == "q":
            print("退出")
            return False  # 停止监听器

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    # 主线程自己跑逻辑，不阻塞
    while listener.is_alive():
        if last_key=="1":
            res=last_key-1
            last_key = None  # 重置一下，避免死循环刷屏
            return res
        elif last_key=="2":
            res = last_key - 1
            last_key = None  # 重置一下，避免死循环刷屏
            return res
        elif last_key=="3":
            res = last_key - 1
            last_key = None  # 重置一下，避免死循环刷屏
            return res
        elif last_key=="4":
            res = last_key - 1
            last_key = None
            return res
