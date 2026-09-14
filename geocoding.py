"""百度地图 WebGL 逆地理编码适配。"""

import hashlib
import json
import os
import random
import re
import time
from urllib.parse import urlencode

import requests
import urllib3

from coordinates import _bd09_to_baidu_mercator, gcj02_to_bd09

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; 2211133C) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
)
# 百度地图 AK 仅从环境变量读取；未配置时由调用方回退为空地点。
BAIDU_AK = os.environ.get("CHECKIN_BAIDU_AK", "").strip()
BAIDU_ABVK_URL = "https://dlswbr.baidu.com/heicha/mw/abclite-2063-s.js"
BAIDU_MAP_URL = "https://api.map.baidu.com/"


def _baidu_sign(raw_query):
    """生成百度 WebGL 请求的 sign。"""
    first = hashlib.md5((raw_query + "F5L2O6R6AD8990O").encode("utf-8")).hexdigest()
    return hashlib.md5((first + "H0A9P8P7Y6ABQO0").encode("utf-8")).hexdigest()[-12:]


def _fetch_baidu_abvk(session):
    """获取百度 WebGL 反滥用会话密钥。"""
    url = BAIDU_ABVK_URL + "?_t=" + str(int(time.time() * 1000))
    response = session.get(url, timeout=20)
    response.raise_for_status()
    match = re.search(r"window\[[^\]]+\]\s*=\s*['\"]([^'\"]+)", response.text)
    if not match:
        match = re.search(r"window\.___abvk\s*=\s*['\"]([^'\"]+)", response.text)
    if not match:
        raise RuntimeError("百度地图响应中没有找到 WebGL 会话密钥")
    return match.group(1)


def reverse_geocode(lng, lat):
    """按前端流程获取实际定位点附近的 POI 名称，失败时由调用方处理。"""
    if not BAIDU_AK:
        raise RuntimeError("未配置 CHECKIN_BAIDU_AK，无法自动识别地点")
    session = requests.Session()
    session.verify = False
    session.headers.update({"Referer": "https://zhxg.csu.edu.cn/znzhxgpt_h5/", "User-Agent": MOBILE_UA})
    abvk = _fetch_baidu_abvk(session)
    bd_lng, bd_lat = gcj02_to_bd09(lng, lat)
    mc_lng, mc_lat = _bd09_to_baidu_mercator(bd_lng, bd_lat)
    callback = "BMapGL._rd._cbk" + str(random.randint(10000, 99999))
    raw_params = [
        ("qt", "rgc"), ("x", repr(mc_lng)), ("y", repr(mc_lat)),
        ("dis_poi", "100"), ("poi_num", "10"), ("latest_admin", "1"),
        ("language", "zh"), ("ie", "utf-8"), ("oue", "1"),
        ("fromproduct", "jsapi"), ("ak", BAIDU_AK), ("res", "api"),
        ("callback", callback), ("v", "gl"), ("seckey", abvk + ",-1"),
        ("timeStamp", str(int(time.time() * 1000))),
    ]
    raw_query = "&".join(f"{key}={value}" for key, value in raw_params)
    url = BAIDU_MAP_URL + "?" + urlencode(raw_params) + "&sign=" + _baidu_sign(raw_query)
    response = session.get(url, timeout=20)
    response.raise_for_status()
    match = re.search(r"\((\{.*\})\)", response.text, re.DOTALL)
    if not match:
        raise RuntimeError("百度地图逆地理编码返回格式异常")
    content = (json.loads(match.group(1)).get("content") or {})
    surrounding = content.get("surround_poi") or []
    if surrounding:
        name = surrounding[0].get("name") or surrounding[0].get("title")
        if name:
            return str(name).strip()
    regions = content.get("poi_region") or []
    if regions and regions[0].get("name"):
        return str(regions[0]["name"]).strip()
    return str(content.get("business") or content.get("address") or "").strip()
