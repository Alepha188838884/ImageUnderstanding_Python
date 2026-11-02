import os
from openai import OpenAI
import time
import config

import base64, pathlib

img_path = "img15.jpeg"     # 绝对或相对路径都行
mime = "jpg"             # 改成 jpg / webp 等
with open(img_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
data_url = f"data:image/{mime};base64,{b64}"

client = OpenAI(
    api_key=config.DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

completion = client.chat.completions.create(
    model="qwen-vl-max", # 此处以qwen-vl-max-latest为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/models
    messages=[
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url
                    },
                },
                {"type": "text", "text": "这张图片中有没有人行道上的控制行人通行的红绿灯？马路对面有没有类似红绿灯的东西？请识别这张图片中的红绿灯，告诉我当前是红灯还是绿灯（或黄灯），并输出倒计时的剩余秒数（注意红绿灯灯管可能的模糊）。如果画面中没有清晰的红绿灯，请直接说明没有检测到。如果是绿灯，你要根据剩余秒数来估算一下我能不能在剩余时间内通过这个路口。如果没有读秒且是绿灯。就说明剩余时间足够"},
            ],
        },
    ],
)
print(completion.choices[0].message.content)