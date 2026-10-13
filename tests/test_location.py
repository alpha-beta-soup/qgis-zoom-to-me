import json
import unittest

from zoom_to_me.location import Location, Source, parse_ipinfo


class ParseIpinfoTests(unittest.TestCase):
    def test_typical_response(self):
        body = json.dumps({
            "ip": "203.0.113.5", "city": "Lincoln", "region": "Canterbury",
            "country": "NZ", "loc": "-43.6400,172.4850", "org": "AS1234 Example",
        })
        loc = parse_ipinfo(body)
        self.assertEqual(loc.source, Source.IP)
        self.assertAlmostEqual(loc.lat, -43.64)
        self.assertAlmostEqual(loc.lon, 172.485)
        self.assertEqual(loc.label, "Lincoln, Canterbury, NZ")
        self.assertIsNone(loc.accuracy_m)

    def test_accepts_bytes(self):
        loc = parse_ipinfo(b'{"loc": "51.5,-0.1", "city": "London"}')
        self.assertEqual((loc.lat, loc.lon), (51.5, -0.1))
        self.assertEqual(loc.label, "London")

    def test_missing_place_names(self):
        loc = parse_ipinfo('{"loc": "0,0"}')
        self.assertEqual(loc.label, "an unnamed place")

    def test_bogon(self):
        with self.assertRaisesRegex(ValueError, "public IP"):
            parse_ipinfo('{"ip": "10.0.0.1", "bogon": true}')

    def test_error_document(self):
        with self.assertRaisesRegex(ValueError, "rate limit"):
            parse_ipinfo('{"error": {"title": "Wrong", "message": "rate limit exceeded"}}')

    def test_missing_loc(self):
        with self.assertRaisesRegex(ValueError, "no location"):
            parse_ipinfo('{"ip": "203.0.113.5", "city": "Nowhere"}')

    def test_not_json(self):
        with self.assertRaisesRegex(ValueError, "not JSON"):
            parse_ipinfo("<html>nope</html>")

    def test_garbage_loc(self):
        with self.assertRaisesRegex(ValueError, "unparseable"):
            parse_ipinfo('{"loc": "north,south"}')

    def test_out_of_range(self):
        with self.assertRaisesRegex(ValueError, "out-of-range"):
            parse_ipinfo('{"loc": "95,10"}')

    def test_non_finite(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            parse_ipinfo('{"loc": "NaN,10"}')


class LocationScaleTests(unittest.TestCase):
    def test_ip_uses_city_scale(self):
        loc = Location(lon=0, lat=0, source=Source.IP, label="x")
        self.assertEqual(loc.scale(), 100000.0)

    def test_gps_default(self):
        loc = Location(lon=0, lat=0, source=Source.GPS, label="GPS fix")
        self.assertEqual(loc.scale(), 5000.0)

    def test_gps_scales_with_accuracy(self):
        loc = Location(lon=0, lat=0, source=Source.GPS, label="GPS fix", accuracy_m=50)
        self.assertEqual(loc.scale(), 10000.0)

    def test_gps_scale_floor(self):
        loc = Location(lon=0, lat=0, source=Source.GPS, label="GPS fix", accuracy_m=1)
        self.assertEqual(loc.scale(), 1000.0)

    def test_describe(self):
        ip = Location(lon=0, lat=0, source=Source.IP, label="Lincoln, Canterbury, NZ")
        self.assertIn("Lincoln, Canterbury, NZ", ip.describe())
        self.assertIn("IP address", ip.describe())
        gps = Location(lon=0, lat=0, source=Source.GPS, label="GPS fix", accuracy_m=4.4)
        self.assertEqual(gps.describe(), "Zoomed to GPS fix, accuracy about 4 m")


if __name__ == "__main__":
    unittest.main()
