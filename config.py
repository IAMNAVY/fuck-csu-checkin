"""本地凭据配置文件读写。"""

import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkin_config.json")
CENTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".checkin-center.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)


def _same_coordinate(saved, current):
    return abs(float(saved) - float(current)) <= 1e-9


def load_center(lng, lat, coord, dklb):
    """读取与当前输入位置匹配的已缓存判定中心。"""
    if not os.path.exists(CENTER_FILE):
        return None
    try:
        with open(CENTER_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)
        source = saved["source"]
        center = saved["center"]
        if (source["coord"] != (coord or "gcj02").lower()
                or source["dklb"] != dklb
                or not _same_coordinate(source["lng"], lng)
                or not _same_coordinate(source["lat"], lat)):
            return None
        center_lng, center_lat = float(center["lng"]), float(center["lat"])
        if not (-180 <= center_lng <= 180 and -90 <= center_lat <= 90):
            return None
        return center_lng, center_lat
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def save_center(lng, lat, coord, dklb, center_lng, center_lat):
    """保存判定中心及其输入坐标元数据；文件仅包含位置数据，不含凭据。"""
    payload = {
        "version": 1,
        "source": {"lng": lng, "lat": lat, "coord": (coord or "gcj02").lower(), "dklb": dklb},
        "center": {"lng": center_lng, "lat": center_lat},
    }
    with open(CENTER_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
