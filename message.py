import json
from datetime import datetime
import requests
import time
import hmac
import hashlib
import base64
from urllib import parse


def cal_timestamp_sign(secret):
    # 根据钉钉开发文档，修改推送消息的安全设置https://ding-doc.dingtalk.com/doc#/serverapi2/qf2nxq
    # 也就是根据这个方法，不只是要有robot_id，还要有secret
    # 当前时间戳，单位是毫秒，与请求调用时间误差不能超过1小时
    # python3用int取整
    timestamp = int(round(time.time() * 1000))
    # 密钥，机器人安全设置页面，加签一栏下面显示SEC开头的字符串
    secret_enc = bytes(secret.encode('utf-8'))
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = bytes(string_to_sign.encode('utf-8'))
    hmac_code = hmac.new(secret_enc, string_to_sign_enc,digestmod=hashlib.sha256).digest()
    # 得到最终的签名值
    sign = parse.quote_plus(base64.b64encode(hmac_code))
    return str(timestamp), str (sign)


def send_dingding_msg(content,
                      robot_id='d2eaa566c6e2473a4855349e468781f5368fba0c6d0fb565c117770ba07a0eba',
                      secret='SECd9c28ad81de55e2ac550fbca8d1c0bcbde8e101cbe64a688187a1bc4abf3b13b'):
    try:
        msg = {"msgtype":"text",
               "text": {"content": content + '\n' + datetime.now().strftime('%m-%d %H:%M:%S')}}
        headers = {"Content-Type": "application/json;charset=utf-8"}
        # https://oapi.dingtalk.com/robot/send?access_to_ken=XXXXXX&timestamp=XXX&sign=XXX
        timestamp, sign_str = cal_timestamp_sign(secret)
        url ='https://oapi.dingtalk.com/robot/send?access_token=' + robot_id +'&timestamp='+ timestamp +'&sign=' + sign_str
        body = json.dumps (msg)
        requests.post(url, data=body, headers=headers)
        print('成功发送钉钉')
    except Exception as e:
        print('发送钉钉失败:', e)

