"""中南大学 CAS 统一认证。"""

import base64
import json
import re
import string
import time
from urllib.parse import quote

import requests
import urllib3

from crypto_utils import _AES_CHARS, _random_string, encrypt_cas_password
from geocoding import MOBILE_UA

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://zhxg.csu.edu.cn/znzhxgpt"
CAS_LOGIN_URL = "https://ca.csu.edu.cn/authserver/login"
CAS_H5_SERVICE = "https://zhxg.csu.edu.cn/fdcwonsun/caslogin_h5.jsp"


class LoginError(Exception):
    """登录过程中出现的错误。"""


def _re_group(pattern, text, group=1):
    match = re.search(pattern, text)
    return match.group(group) if match else None


def cas_login(username, password):
    """完成 CAS 认证、换票和 login-other，返回 token、casual、姓名、学号。"""
    session = requests.Session()
    session.headers.update({"User-Agent": MOBILE_UA})
    session.verify = False
    login_url = CAS_LOGIN_URL + "?service=" + quote(CAS_H5_SERVICE, safe="")

    print("[登录 1/4] 访问 CAS 登录页 ...")
    try:
        html = session.get(login_url, timeout=20).text
    except requests.RequestException as exc:
        raise LoginError(f"无法访问 CAS 登录页：{exc}")
    salt = _re_group(r'id="pwdEncryptSalt" value="([^"]*)"', html)
    execution = _re_group(r'name="execution" value="([^"]*)"', html)
    if not salt:
        raise LoginError("未在登录页解析到 pwdEncryptSalt")
    if not execution:
        raise LoginError("未在登录页解析到 execution")

    print("[登录 2/4] 提交账号密码 ...")
    data = {
        "username": username,
        "password": encrypt_cas_password(password, salt),
        "captcha": "",
        "_eventId": "submit",
        "lt": "",
        "cllt": "userNameLogin",
        "dllt": "generalLogin",
        "execution": execution,
    }
    try:
        response = session.post(login_url, data=data, allow_redirects=False, timeout=20)
    except requests.RequestException as exc:
        raise LoginError(f"提交 CAS 登录失败：{exc}")
    match = re.search(r"[?&]ticket=([^&]+)", response.headers.get("Location", ""))
    if response.status_code not in (302, 303) or not match:
        raise LoginError("CAS 登录失败，未获取到 ticket（账号或密码错误，或连续失败触发验证码）")
    ticket = match.group(1)

    print("[登录 3/4] 换取 uid / lzc ...")
    try:
        response = session.get(CAS_H5_SERVICE + "?ticket=" + quote(ticket, safe=""), allow_redirects=True, timeout=20)
    except requests.RequestException as exc:
        raise LoginError(f"访问 caslogin_h5.jsp 失败：{exc}")
    uid = _re_group(r"var uid = '([^']+)'", response.text)
    lzc = _re_group(r"var lzc = '([^']+)'", response.text)
    if not uid or not lzc:
        raise LoginError("caslogin_h5.jsp 未返回 uid/lzc")

    print("[登录 4/4] 调用 login-other 获取 token ...")
    casual = _random_string(16, string.ascii_letters + string.digits)
    body = {
        "tyrzpt": "1", "channeld": "1",
        "yhzh": quote(quote(uid, safe=""), safe=""),
        "lzc": quote(quote(lzc, safe=""), safe=""),
        "caasual": casual,
    }
    headers = {
        "Content-Type": "application/json; charset=UTF-8", "AppCode": "znzhxgpt",
        "Origin": "https://zhxg.csu.edu.cn", "Referer": "https://zhxg.csu.edu.cn/znzhxgpt_h5/",
        "Accept": "*/*", "deviceType": "4",
    }
    try:
        response = session.post(BASE_URL + "/basesys/rbac-yh/login-other", data=json.dumps(body, ensure_ascii=False), headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise LoginError(f"login-other 请求失败：{exc}")
    result = response.json()
    if str(result.get("code")) != "200":
        raise LoginError(f"login-other 返回错误：{result.get('message')}")
    details = result.get("data") or {}
    token = details.get("token")
    if not token:
        raise LoginError("login-other 未返回 token")
    return token, _jwt_user_token(token) or casual, details.get("yhxm") or "", details.get("yhzh") or ""


def _jwt_user_token(token):
    """从 JWT payload 解析 user_info.userToken。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        obj = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        user_info = obj.get("user_info")
        if isinstance(user_info, str):
            user_info = json.loads(user_info)
        return (user_info or {}).get("userToken")
    except Exception:
        return None


def _token_expired(token):
    """判断 JWT token 是否已过期。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8")).get("exp")
        return bool(exp) and exp < time.time()
    except Exception:
        return False
