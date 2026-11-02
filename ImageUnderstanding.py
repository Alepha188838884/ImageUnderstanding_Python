import _thread as thread
import base64
import datetime
import hashlib
import hmac
import json
from urllib.parse import urlparse
import ssl
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
import websocket  # 使用websocket_client
import config
import supersmart_tts

answer = ""
activation_word = ["看红绿灯", "看盲道", "看菜单", "看周围"]
prompt_list = [
    """我是一个盲人，请告诉我这张图片中有没有人行道上的控制行人通行的红绿灯？马路对面有没有类似红绿灯的东西？
                 请识别这张图片中的红绿灯，告诉我当前是红灯还是绿灯（或黄灯），并输出倒计时的剩余秒数（注意红绿灯灯管可能的模糊）。
                 如果画面中没有清晰的红绿灯，请直接说明没有检测到。如果是绿灯，你要根据剩余秒数来估算一下我能不能在剩余时间内通过这个路口。
                 如果没有读秒且是绿灯。就说明剩余时间足够。同时你来预测一下这个路口长多少米""",
    """我是一个盲人，请识别图片或视频中的盲道，标出其位置，并判断盲道是否连续、是否被障碍物占用或遮挡。
                 请用简洁文字描述盲道的状态，如果盲道有遮挡，请告诉我怎么绕过去。你需要注意盲道附近是否还有别的障碍物，再判断绕行方案。""",
    """我是一个盲人，请识别这张图片中的书本文字，并逐行提取为清晰可读的文本。如果有段落或标题，请保持排版格式。确保输出完整准确。""",
    """我是一个盲人，请对画面中的周围环境进行整体描述，包括：主要物体（如建筑、车辆、行人）、它们的大致位置、
                 以及与我行动相关的关键信息（如道路方向、障碍物、交通标志）。请简洁明了地总结环境情况。""",
    """请看一下摄像头上有没有污点，或者是被遮挡。如果有被遮挡或者是有污点，请回答。否则不要回答""",
]
action_prompts = dict(zip(activation_word, prompt_list[:4]))
WAKE_WORD = "智能助手"


def build_next(pat: str):
    """构造模式串的 next 数组"""
    m = len(pat)
    nxt = [0] * m
    j = 0
    for i in range(1, m):
        while j > 0 and pat[i] != pat[j]:
            j = nxt[j - 1]
        if pat[i] == pat[j]:
            j += 1
        nxt[i] = j
    return nxt


def kmp_search(txt: str, pat: str):
    """KMP 搜索，返回所有匹配起点下标"""
    n, m = len(txt), len(pat)
    if m == 0:
        return []
    nxt = build_next(pat)
    res = []
    j = 0
    for i in range(n):
        while j > 0 and txt[i] != pat[j]:
            j = nxt[j - 1]
        if txt[i] == pat[j]:
            j += 1
        if j == m:
            res.append(i - m + 1)
            j = nxt[j - 1]
    return res


def match_activation_command(voice_input: str):
    """从语音文本里匹配预设功能词"""
    if not voice_input:
        return None
    for key in activation_word:
        if kmp_search(voice_input, key):
            return key
    return None


def main_program(image_path, action_word=None):
    global answer

    appid = config.XFYUN_APP_ID
    api_secret = config.XFYUN_API_SECRET
    api_key = config.XFYUN_API_KEY

    imagedata = open(image_path, 'rb').read()
    imageunderstanding_url = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"#云端环境的服务地址
    text = [{"role": "user", "content": str(base64.b64encode(imagedata), 'utf-8'), "content_type": "image"}]



    class Ws_Param(object):
        # 初始化
        def __init__(self, APPID, APIKey, APISecret, imageunderstanding_url):
            self.APPID = APPID
            self.APIKey = APIKey
            self.APISecret = APISecret
            self.host = urlparse(imageunderstanding_url).netloc
            self.path = urlparse(imageunderstanding_url).path
            self.ImageUnderstanding_url = imageunderstanding_url

        # 生成url
        def create_url(self):
            # 生成RFC1123格式的时间戳
            now = datetime.now()
            date = format_date_time(mktime(now.timetuple()))

            # 拼接字符串
            signature_origin = "host: " + self.host + "\n"
            signature_origin += "date: " + date + "\n"
            signature_origin += "GET " + self.path + " HTTP/1.1"

            # 进行hmac-sha256进行加密
            signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                     digestmod=hashlib.sha256).digest()

            signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

            authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

            authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

            # 将请求的鉴权参数组合为字典
            v = {
                "authorization": authorization,
                "date": date,
                "host": self.host
            }
            # 拼接鉴权参数，生成url
            url = self.ImageUnderstanding_url + '?' + urlencode(v)
            #print(url)
            # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
            return url


    # 收到websocket错误的处理
    def on_error(ws, error):
        print("### error:", error)


    # 收到websocket关闭的处理
    def on_close(ws,one,two):
        print(" ")


    # 收到websocket连接建立的处理
    def on_open(ws):
        thread.start_new_thread(run, (ws,))


    def run(ws, *args):
        data = json.dumps(gen_params(appid=ws.appid, question= ws.question ))
        ws.send(data)


    # 收到websocket消息的处理
    def on_message(ws, message):
        #print(message)
        data = json.loads(message)
        code = data['header']['code']
        if code != 0:
            print(f'请求错误: {code}, {data}')
            ws.close()
        else:
            choices = data["payload"]["choices"]
            status = choices["status"]
            content = choices["text"][0]["content"]
            print(content,end ="")
            global answer
            answer += content
            # print(1)
            if status == 2:
                ws.close()


    def gen_params(appid, question):
        """
        通过appid和用户的提问来生成请参数
        """

        data = {
            "header": {
                "app_id": appid
            },
            "parameter": {
                "chat": {
                    "domain": "imagev3",
                    "temperature": 0.5,
                    "top_k": 4,
                    "max_tokens": 2028,
                    "auditing": "default"
                }
            },
            "payload": {
                "message": {
                    "text": question
                }
            }
    }

        return data


    def main(appid, api_key, api_secret, imageunderstanding_url,question):

        wsParam = Ws_Param(appid, api_key, api_secret, imageunderstanding_url)
        websocket.enableTrace(False)
        wsUrl = wsParam.create_url()
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
        ws.appid = appid
        #ws.imagedata = imagedata
        ws.question = question
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})


    def getText(role, content):
        jsoncon = {}
        jsoncon["role"] = role
        jsoncon["content"] = content
        text.append(jsoncon)
        return text


    def getlength(text):
        length = 0
        for content in text:
            temp = content["content"]
            leng = len(temp)
            length += leng
        return length


    def checklen(text):
        #print("text-content-tokens:", getlength(text[1:]))
        while (getlength(text[1:])> 8000):
            del text[1]
        return text

    def ask_with_prompt(prompt_text):
        global answer
        question = checklen(getText("user", prompt_text))
        answer = ""
        print("答:", end="")
        main(appid, api_key, api_secret, imageunderstanding_url, question)
        getText("assistant", answer)
        cleaned = answer.replace(" ", "")
        supersmart_tts.func(cleaned)
        return cleaned

    # 初始检测：摄像头上有没有污点或者是被遮挡
    ask_with_prompt(prompt_list[4])

    selected_action = None
    if action_word:
        selected_action = match_activation_command(action_word)
        if not selected_action and action_word in action_prompts:
            selected_action = action_word
    if selected_action is None:
        try:
            idx = int(input("请输入编号：")) - 1
            if 0 <= idx < len(activation_word):
                selected_action = activation_word[idx]
        except Exception:
            selected_action = None

    if not selected_action:
        print(f"未识别到有效的功能指令，支持：{'、'.join(activation_word)}")
        return ""

    prompt_to_use = action_prompts.get(selected_action)
    if not prompt_to_use:
        print(f"未找到对应的提示词: {selected_action}")
        return ""

    return ask_with_prompt(prompt_to_use)
