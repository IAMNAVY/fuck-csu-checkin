"""中南大学智慧学工接口客户端。"""

import json

import requests
import urllib3

from crypto_utils import des_encrypt
from geocoding import MOBILE_UA

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://zhxg.csu.edu.cn/znzhxgpt"
QXJ_URL = BASE_URL + "/qxj"
DKLB_DEFAULT = "PA"


def _decode(resp):
    """正确解码响应：优先 UTF-8，出现乱码则回退 GBK。"""
    raw = resp.content
    for encoding in ("utf-8", "gbk"):
        try:
            text = raw.decode(encoding)
            if "�" not in text:
                return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


class CheckinClient:
    def __init__(self, token, casual):
        self.token = token
        self.casual = casual
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Authorization": token,
            "token": token,
            "AppCode": "znzhxgpt",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://zhxg.csu.edu.cn",
            "Referer": "https://zhxg.csu.edu.cn/znzhxgpt_h5/",
            "User-Agent": MOBILE_UA,
            "Accept": "*/*",
            "deviceType": "4",
        })

    def _post_des(self, url, payload):
        response = self.session.post(url, data=des_encrypt(payload, self.casual), timeout=20)
        return _decode(response)

    def query_dkbc(self, dklb=DKLB_DEFAULT):
        """查询打卡班次，返回接口 data 字段。"""
        return self._post_des(QXJ_URL + "/qxj-padkglxx/queryKqDkbc", {"paramsData": {"dklb": dklb}})

    def check_range(self, lng, lat, dklb=DKLB_DEFAULT):
        """校验坐标是否在打卡范围内。"""
        return self._post_des(QXJ_URL + "/qxj-padkglxx/jcqqwzsjsfndk", {"paramsData": {"jd": lng, "wd": lat, "dklb": dklb}})

    def submit(self, lng, lat, dkbc, dkdz=""):
        """上报打卡；dkdz 由实际定位点的逆地理编码得到。"""
        return self._post_des(QXJ_URL + "/qxj-padkglxx/xspadk", {"jd": lng, "wd": lat, "dkbc": dkbc, "dkdz": dkdz})
