"""请求体与 CAS 密码加密工具。"""

import base64
import json
import random
import string

from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad

_AES_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"


def des_encrypt(payload_dict, casual):
    """DES-ECB + PKCS7 加密接口请求体。"""
    key = (casual or "").encode("utf-8")[:8].ljust(8, b"\x00")
    body = json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cipher = DES.new(key, DES.MODE_ECB)
    return cipher.encrypt(pad(body, 8)).hex()


def _random_string(n, alphabet):
    return "".join(random.choices(alphabet, k=n))


def encrypt_cas_password(password, salt):
    """使用 CAS 页面约定的 AES-128-CBC 方式加密密码。"""
    key = (salt or "").encode("utf-8")[:16].ljust(16, b"\x00")
    iv = _random_string(16, _AES_CHARS).encode("utf-8")
    plaintext = (_random_string(64, _AES_CHARS) + password).encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return base64.b64encode(cipher.encrypt(pad(plaintext, 16))).decode()
