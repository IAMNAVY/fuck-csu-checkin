#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中南大学智慧学工打卡脚本的兼容入口。

具体实现按职责拆分在 coordinates、geocoding、crypto_utils、auth、api、config
和 cli 模块中；保留本文件以兼容原来的 ``python checkin.py`` 用法。
"""

from api import CheckinClient, DKLB_DEFAULT, QXJ_URL, _decode
from auth import (
    BASE_URL,
    CAS_H5_SERVICE,
    CAS_LOGIN_URL,
    LoginError,
    _jwt_user_token,
    _re_group,
    _token_expired,
    cas_login,
)
from cli import main, prompt_float
from config import CONFIG_FILE, load_config, save_config
from coordinates import (
    RANDOM_POINT_RADIUS_M,
    _BD09_MC_BANDS,
    _BD09_MC_COEFFICIENTS,
    _BD09_MC_LAT_BANDS,
    _bd09_to_baidu_mercator,
    _out_of_china,
    _transform_lat,
    _transform_lng,
    bd09_to_gcj02,
    gcj02_to_bd09,
    random_point_within_radius,
    to_gcj02,
    wgs84_to_gcj02,
)
from crypto_utils import _AES_CHARS, _random_string, des_encrypt, encrypt_cas_password
from geocoding import (
    BAIDU_ABVK_URL,
    BAIDU_MAP_URL,
    MOBILE_UA,
    _baidu_sign,
    _fetch_baidu_abvk,
    reverse_geocode,
)


if __name__ == "__main__":
    main()
