import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from coordinates import (  # noqa: E402
    RANDOM_POINT_RADIUS_M,
    _local_point,
    estimate_center,
    random_point_within_radius,
)


class CenterClient:
    def __init__(self, origin_lng, origin_lat, center_east, center_north, distances=None):
        self.origin_lng = origin_lng
        self.origin_lat = origin_lat
        self.center_east = center_east
        self.center_north = center_north
        self.distances = iter(distances) if distances else None
        self.calls = []

    def check_range(self, lng, lat, dklb):
        self.calls.append((lng, lat, dklb))
        if self.distances:
            distance = next(self.distances)
        else:
            east, north = _local_point(lng, lat, self.origin_lng, self.origin_lat)
            distance = round(math.hypot(east - self.center_east, north - self.center_north))
        return {"code": "200", "data": {"pcMi": distance}}


class CoordinateTests(unittest.TestCase):
    def test_estimate_center_from_rounded_distances(self):
        origin = (112.936833, 28.157238)
        expected = (-175.0, 85.0)
        client = CenterClient(*origin, *expected)

        center = estimate_center(client, *origin)

        actual = _local_point(*center, *origin)
        self.assertAlmostEqual(actual[0], expected[0], delta=2)
        self.assertAlmostEqual(actual[1], expected[1], delta=2)
        self.assertEqual(len(client.calls), 3)

    def test_estimate_center_rejects_inconsistent_distances(self):
        origin = (112.936833, 28.157238)
        client = CenterClient(*origin, 0, 0, distances=(100, 200, 300))

        with self.assertRaisesRegex(ValueError, "残差过大"):
            estimate_center(client, *origin)

    def test_random_point_uses_100_metre_radius(self):
        lng, lat = random_point_within_radius(112.936833, 28.157238)
        east, north = _local_point(lng, lat, 112.936833, 28.157238)

        self.assertLessEqual(math.hypot(east, north), RANDOM_POINT_RADIUS_M + 0.01)

    def test_center_cache_matches_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            original_file = config.CENTER_FILE
            config.CENTER_FILE = str(Path(directory) / ".checkin-center.json")
            try:
                config.save_center(112.9, 28.1, "gcj02", "PA", 112.8, 28.2)
                self.assertEqual(config.load_center(112.9, 28.1, "gcj02", "PA"), (112.8, 28.2))
                self.assertIsNone(config.load_center(112.9, 28.1001, "gcj02", "PA"))
            finally:
                config.CENTER_FILE = original_file


if __name__ == "__main__":
    unittest.main()
