"""坐标系统转换与随机定位点工具。"""

import math
import random

_PI = math.pi
_A = 6378245.0
_EE = 0.006693421622965943
_X_PI = _PI * 3000.0 / 180.0
RANDOM_POINT_RADIUS_M = 100.0
_EARTH_RADIUS_M = 6_371_000.0
_CENTER_PROBE_OFFSET_M = 120.0
_CENTER_MAX_RESIDUAL_M = 10.0
_CENTER_PROBE_OFFSETS = ((0.0, 0.0), (_CENTER_PROBE_OFFSET_M, 0.0), (0.0, _CENTER_PROBE_OFFSET_M))


def _out_of_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng, lat):
    ret = 2.0 * lng - 100.0 + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * _PI) + 20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * _PI) + 40.0 * math.sin(lat / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * _PI) + 320.0 * math.sin(lat * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * _PI) + 20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * _PI) + 40.0 * math.sin(lng / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * _PI) + 300.0 * math.sin(lng / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng, lat):
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _PI
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * _PI)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * _PI)
    return lng + dlng, lat + dlat


def gcj02_to_bd09(lng, lat):
    x, y = lng, lat
    z = math.sqrt(x * x + y * y) + 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) + 0.000003 * math.cos(x * _X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def bd09_to_gcj02(lng, lat):
    x, y = lng - 0.0065, lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return z * math.cos(theta), z * math.sin(theta)


_BD09_MC_BANDS = (12890594.86, 8362377.87, 5591021.0, 3481989.83, 1678043.12, 0.0)
_BD09_MC_LAT_BANDS = (75.0, 60.0, 45.0, 30.0, 15.0, 0.0)
_BD09_MC_COEFFICIENTS = (
    (-0.0015702102444, 111320.7020616939, 1704480524535203.0, -10338987376042340.0, 26112667856603880.0, -35149669176653700.0, 26595700718403920.0, -10725012454188240.0, 1800819912950474.0, 82.5),
    (0.0008277824516172526, 111320.7020463578, 647795574.6671607, -4082003173.641316, 10774905663.51142, -15171875531.51559, 913311935.9512032, -5124939663.577472, 913311935.9512032, 67.5),
    (0.00337398766765, 111320.7020202162, 4481351.045890365, -23393751.19931662, 79682215.47186455, -115964993.2797253, 97236711.15602145, -43661946.33752821, 8477230.501135234, 52.5),
    (0.00220636496208, 111320.7020209128, 51751.86112841131, 3796837.749470245, 992013.7397791013, -1221952.21711287, 1340652.697009075, -620943.6990984312, 144416.9293806241, 37.5),
    (-0.0003441963504368392, 111320.7020576856, 278.2353980772752, 2485758.690035394, 6070.750963243378, 54821.18345352118, 9540.606633304236, -2710.55326746645, 1405.483844121726, 22.5),
    (-0.0003218135878613132, 111320.7020701615, 0.00369383431289, 823725.6402795718, 0.46104986909093, 2351.343141331292, 1.58060784298199, 8.77738589078284, 0.37238884252424, 7.45),
)


def _bd09_to_baidu_mercator(lng, lat):
    """把 BD-09 经纬度转换为百度地图 WebGL 接口使用的平面坐标。"""
    coefficients = _BD09_MC_COEFFICIENTS[-1]
    abs_lat = abs(lat)
    for band, limit in zip(_BD09_MC_COEFFICIENTS, _BD09_MC_LAT_BANDS):
        if abs_lat > limit:
            coefficients = band
            break
    normalized_lat = abs_lat / coefficients[9]
    x = coefficients[0] + coefficients[1] * abs(lng)
    y = coefficients[2]
    for power, coefficient in enumerate(coefficients[3:9], start=1):
        y += coefficient * normalized_lat ** power
    return x * (-1 if lng < 0 else 1), y * (-1 if lat < 0 else 1)


def to_gcj02(lng, lat, coord):
    """把输入坐标统一转成 GCJ-02。"""
    coord = (coord or "gcj02").lower()
    if coord == "wgs84":
        return wgs84_to_gcj02(lng, lat)
    if coord == "bd09":
        return bd09_to_gcj02(lng, lat)
    return lng, lat


def _offset_point(lng, lat, east_m, north_m):
    lat_rad = math.radians(lat)
    meters_per_degree_lng = _EARTH_RADIUS_M * math.cos(lat_rad)
    if abs(meters_per_degree_lng) < 1e-12:
        raise ValueError("纬度过于接近极点，无法生成查询经度")
    return (
        lng + math.degrees(east_m / meters_per_degree_lng),
        lat + math.degrees(north_m / _EARTH_RADIUS_M),
    )


def _local_point(lng, lat, origin_lng, origin_lat):
    lat_rad = math.radians(origin_lat)
    return (
        math.radians(lng - origin_lng) * _EARTH_RADIUS_M * math.cos(lat_rad),
        math.radians(lat - origin_lat) * _EARTH_RADIUS_M,
    )


def _pcmi(data):
    if not isinstance(data, dict):
        return None
    try:
        distance = float(data.get("pcMi"))
    except (TypeError, ValueError):
        return None
    return distance if math.isfinite(distance) and distance >= 0 else None


def _fit_center(points, distances):
    if len(points) != len(distances) or len(points) < 3:
        return None
    x1, y1 = points[0]
    d1 = distances[0]
    rows = []
    for (xi, yi), di in zip(points[1:], distances[1:]):
        rows.append((
            2 * (xi - x1),
            2 * (yi - y1),
            d1 * d1 - di * di + xi * xi + yi * yi - x1 * x1 - y1 * y1,
        ))
    (a1, b1, c1), (a2, b2, c2) = rows
    determinant = a1 * b2 - a2 * b1
    if abs(determinant) < 1e-9:
        return None
    return ((c1 * b2 - c2 * b1) / determinant,
            (a1 * c2 - a2 * c1) / determinant)


def estimate_center(client, lng, lat, dklb="PA"):
    """用三个实时 pcMi 查询估算固定判定中心，返回 GCJ-02 经纬度。"""
    points = []
    distances = []
    for east_m, north_m in _CENTER_PROBE_OFFSETS:
        query_lng, query_lat = _offset_point(lng, lat, east_m, north_m)
        response = client.check_range(query_lng, query_lat, dklb)
        if not isinstance(response, dict) or str(response.get("code")) != "200":
            raise ValueError(f"中心探测接口返回异常：{response.get('message') if isinstance(response, dict) else response}")
        data = response.get("data") or {}
        distance = _pcmi(data)
        if distance is None:
            raise ValueError("中心探测未返回有效 pcMi（可能不在打卡时段内）")
        points.append(_local_point(query_lng, query_lat, lng, lat))
        distances.append(distance)

    center = _fit_center(points, distances)
    if center is None:
        raise ValueError("中心探测点几何退化，无法估算")
    residuals = [math.hypot(px - center[0], py - center[1]) - distance
                 for (px, py), distance in zip(points, distances)]
    if max(abs(residual) for residual in residuals) > _CENTER_MAX_RESIDUAL_M:
        raise ValueError(f"中心探测残差过大（最大 {max(abs(residual) for residual in residuals):.1f} 米）")
    return _offset_point(lng, lat, *center)


def random_point_within_radius(lng, lat, radius_m=RANDOM_POINT_RADIUS_M):
    """在 GCJ-02 坐标圆心周围均匀生成一个半径内的随机点。"""
    if radius_m < 0:
        raise ValueError("随机点半径不能为负数")
    distance = math.sqrt(random.random()) * radius_m
    bearing = random.random() * 2.0 * _PI
    meters_per_degree_lat = 111320.0
    meters_per_degree_lng = meters_per_degree_lat * math.cos(math.radians(lat))
    if abs(meters_per_degree_lng) < 1e-12:
        raise ValueError("纬度过于接近极点，无法生成随机经度")
    offset_lng = distance * math.cos(bearing) / meters_per_degree_lng
    offset_lat = distance * math.sin(bearing) / meters_per_degree_lat
    return lng + offset_lng, lat + offset_lat
