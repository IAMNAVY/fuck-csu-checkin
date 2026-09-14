"""命令行交互与打卡流程。"""

import argparse
import getpass
import json
import os
import sys

import requests

from api import CheckinClient, DKLB_DEFAULT
from auth import LoginError, _token_expired, cas_login
from config import CONFIG_FILE, load_config, save_config
from coordinates import RANDOM_POINT_RADIUS_M, random_point_within_radius, to_gcj02
from geocoding import reverse_geocode

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_ENV_COORD = "CHECKIN_COORD"
_ENV_DKLB = "CHECKIN_DKLB"


def prompt_float(name, default=None):
    while True:
        raw = input(f"请输入{name}（浮点数）: ").strip()
        if not raw and default is not None:
            return default
        try:
            return float(raw)
        except ValueError:
            print("  输入不是合法数字，请重试。")


def _env_float(name):
    """读取环境变量中的坐标，错误时给出适合 CI 日志的提示。"""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {name} 不是合法数字：{raw!r}") from exc


def _running_non_interactively():
    """GitHub Actions 等无终端环境不能等待 input。"""
    return not sys.stdin.isatty() or os.environ.get("CI", "").lower() == "true"


def _get_coordinates(args):
    lng = args.lng if args.lng is not None else _env_float("CHECKIN_LNG")
    lat = args.lat if args.lat is not None else _env_float("CHECKIN_LAT")
    if lng is None and not _running_non_interactively():
        lng = prompt_float("经度")
    if lat is None and not _running_non_interactively():
        lat = prompt_float("纬度")
    if lng is None or lat is None:
        raise ValueError("缺少经纬度，请设置 CHECKIN_LNG/CHECKIN_LAT 或传入 --lng/--lat")
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        raise ValueError("经纬度超出合法范围")
    return lng, lat


def _load_auth(args, config):
    """优先读取 token/casual，其次使用账号密码登录。"""
    token = args.token or config.get("token") or os.environ.get("CHECKIN_TOKEN")
    casual = args.casual or config.get("casual") or os.environ.get("CHECKIN_CASUAL")
    username = args.username or os.environ.get("CHECKIN_USERNAME")
    password = os.environ.get("CHECKIN_PASSWORD")

    if token and _token_expired(token):
        print("检测到 token 已过期，将重新登录 ...")
        token = casual = None

    if token and casual:
        return token, casual

    if _running_non_interactively():
        if not username or not password:
            raise LoginError(
                "非交互模式缺少认证信息，请设置 CHECKIN_TOKEN + CHECKIN_CASUAL，"
                "或设置 CHECKIN_USERNAME + CHECKIN_PASSWORD"
            )
    elif args.token or args.casual:
        if not token:
            token = input("请输入 token: ").strip()
        if not casual:
            casual = input("请输入 casual（16 位密钥）: ").strip()
        if token and casual:
            return token, casual
    else:
        username = username or input("请输入学号/账号: ").strip()
        password = password or getpass.getpass("请输入密码: ")

    if not username or not password:
        raise LoginError("账号或密码为空，无法继续")
    print("使用账号密码登录 ...")
    token, casual, name, student_id = cas_login(username, password)
    print(f"登录成功：{name}（学号 {student_id}）")
    return token, casual


def main():
    parser = argparse.ArgumentParser(description="中南大学智慧学工打卡上报")
    parser.add_argument("--lng", type=float, help="经度")
    parser.add_argument("--lat", type=float, help="纬度")
    parser.add_argument("--coord", choices=["gcj02", "wgs84", "bd09"], default=os.environ.get(_ENV_COORD) or "gcj02", help="输入坐标系统，默认 gcj02")
    parser.add_argument("--dklb", default=os.environ.get(_ENV_DKLB) or DKLB_DEFAULT, help="打卡类别，默认 PA")
    parser.add_argument("--dkdz", help="手动指定上报地点；默认根据实际定位点自动识别")
    parser.add_argument("--token", help="JWT token（缺省则读配置/环境变量）")
    parser.add_argument("--casual", help="DES 密钥 casual（16 位）")
    parser.add_argument("--username", help="账号（缺省则读 CHECKIN_USERNAME）")
    parser.add_argument("--dry-run", action="store_true", help="只查询+校验，不真正打卡")
    args = parser.parse_args()

    config = load_config()
    try:
        token, casual = _load_auth(args, config)
        if config.get("token") != token or config.get("casual") != casual:
            # GitHub Actions 工作区短暂且可能只读，不把凭据写回仓库。
            if not _running_non_interactively() and not os.environ.get("CI"):
                config["token"] = token
                config["casual"] = casual
                save_config(config)
                print(f"已保存 token / casual 到 {CONFIG_FILE}\n")

        lng, lat = _get_coordinates(args)
        center_lng, center_lat = to_gcj02(lng, lat, args.coord)
        report_lng, report_lat = random_point_within_radius(center_lng, center_lat, RANDOM_POINT_RADIUS_M)
        print(f"\n输入圆心: ({lng}, {lat}) [{args.coord}]")
        print(f"转换圆心: ({center_lng:.10f}, {center_lat:.10f}) [GCJ-02]")
        print(f"第一次定位点（半径 {RANDOM_POINT_RADIUS_M:.0f}m 内）:")
        print(f"  ({report_lng:.10f}, {report_lat:.10f}) [GCJ-02]")

        if args.dkdz or os.environ.get("CHECKIN_DKDZ"):
            dkdz = (args.dkdz or os.environ.get("CHECKIN_DKDZ") or "").strip()
            print(f"手动指定上报地点: {dkdz}")
        elif not os.environ.get("CHECKIN_BAIDU_AK", "").strip():
            dkdz = ""
            print("未配置 CHECKIN_BAIDU_AK，跳过自动地点识别，将以空地点上报。")
        else:
            print("正在根据实际定位点识别地点 ...")
            try:
                dkdz = reverse_geocode(report_lng, report_lat)
            except (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                dkdz = ""
                print(f"  ⚠️ 地点识别失败，将以空地点上报：{exc}")
            if dkdz:
                print(f"自动识别地点: {dkdz}")
            else:
                print("  ⚠️ 未识别到附近地点，将以空地点上报。")

        client = CheckinClient(token, casual)
        print("\n[1/3] 查询打卡班次 ...")
        info = client.query_dkbc(args.dklb)
        if str(info.get("code")) not in ("200",):
            print("  查询失败：", info.get("message"))
            return 1
        data = info.get("data") or {}
        dkbc = data.get("dkbc") or ""
        print(f"  打卡班次: {dkbc}")
        print(f"  打卡时段: {data.get('dksjfw')}")
        print(f"  是否可打: {data.get('kdk')}  是否已打: {data.get('sfydk')}")
        if not dkbc:
            print("  未取到 dkbc，无法上报。")
            return 1
        if not data.get("kdk"):
            print("  当前不在打卡时段内，无法打卡。")
            return 1

        print("\n[2/3] 校验坐标范围 ...")
        range_result = client.check_range(report_lng, report_lat, args.dklb)
        if str(range_result.get("code")) in ("200",) and isinstance(range_result.get("data"), dict):
            details = range_result["data"]
            print(f"  是否在范围内: {details.get('canDk')}")
            print(f"  距离: {details.get('pcMi')} 米  范围: {details.get('fwMi')} 米  楼栋: {details.get('yxMc')}")
            if details.get("canDk") is False and not args.dry_run:
                print("  提示：不在打卡范围内，上报可能失败，仍继续尝试...")
        else:
            print("  范围校验返回异常：", range_result.get("message"))

        if args.dry_run:
            print("\n[dry-run] 跳过真正上报。")
            return 0

        print("\n[3/3] 上报打卡 ...")
        result = client.submit(report_lng, report_lat, dkbc, dkdz=dkdz)
        if str(result.get("code")) in ("200",):
            print(f"  ✅ 打卡成功！地点：{dkdz}")
            return 0
        print("  ❌ 打卡失败：", result.get("message"))
        return 1
    except (LoginError, ValueError, requests.RequestException, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
