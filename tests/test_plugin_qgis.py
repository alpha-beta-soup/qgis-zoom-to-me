"""Tests for the QGIS-bound part of the plugin.

These need the qgis Python package, so they are skipped under plain Python.
Run them with `make test-qgis`, which uses the conda QGIS environment.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsPointXY
    from qgis.gui import QgsMapCanvas
    from qgis.PyQt.QtCore import QByteArray
    from qgis.PyQt.QtNetwork import QNetworkReply
    HAVE_QGIS = True
except ImportError:  # pragma: no cover
    HAVE_QGIS = False

from zoom_to_me.location import Location, Source

APP = None


def setUpModule():
    global APP
    if HAVE_QGIS:
        APP = QgsApplication([], True)
        APP.initQgis()


def tearDownModule():
    if APP is not None:
        APP.exitQgis()


class FakeMessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, title, text, level=None, duration=None):
        self.messages.append((title, text, level))


class FakeIface:
    def __init__(self):
        self.canvas = QgsMapCanvas()
        self.canvas.resize(800, 600)
        self.bar = FakeMessageBar()
        self.toolbar_actions = []
        self.menu_actions = []

    def mapCanvas(self):
        return self.canvas

    def messageBar(self):
        return self.bar

    def mainWindow(self):
        return None

    def addToolBarIcon(self, action):
        self.toolbar_actions.append(action)

    def removeToolBarIcon(self, action):
        self.toolbar_actions.remove(action)

    def addPluginToMenu(self, name, action):
        self.menu_actions.append(action)

    def removePluginMenu(self, name, action):
        self.menu_actions.remove(action)


class FakeReply:
    def __init__(self, body=b"", error=None, error_string=""):
        self.body = body
        self._error = QNetworkReply.NetworkError.NoError if error is None else error
        self._error_string = error_string
        self.deleted = False

    def error(self):
        return self._error

    def errorString(self):
        return self._error_string

    def readAll(self):
        return QByteArray(self.body)

    def deleteLater(self):
        self.deleted = True

    def abort(self):
        pass


LINCOLN = Location(lon=172.485, lat=-43.64, source=Source.IP, label="Lincoln, Canterbury, NZ")


@unittest.skipUnless(HAVE_QGIS, "qgis Python package not importable")
class PluginTests(unittest.TestCase):
    def setUp(self):
        from zoom_to_me.plugin import ZoomToMePlugin
        self.iface = FakeIface()
        self.plugin = ZoomToMePlugin(self.iface)
        self.plugin.initGui()

    def tearDown(self):
        self.plugin.unload()

    def test_init_and_unload_manage_action(self):
        self.assertEqual(len(self.iface.toolbar_actions), 1)
        self.assertEqual(len(self.iface.menu_actions), 1)
        self.assertEqual(self.iface.toolbar_actions[0].text(), "Zoom to me")
        self.plugin.unload()
        self.assertEqual(self.iface.toolbar_actions, [])
        self.assertEqual(self.iface.menu_actions, [])
        self.assertIsNone(self.plugin.action)

    def test_zoom_in_wgs84_project(self):
        self.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.plugin._zoom_to(LINCOLN)
        centre = self.iface.canvas.center()
        self.assertAlmostEqual(centre.x(), LINCOLN.lon, places=4)
        self.assertAlmostEqual(centre.y(), LINCOLN.lat, places=4)
        self.assertAlmostEqual(self.iface.canvas.scale(), 100000, delta=100000 * 0.02)

    def test_zoom_transforms_into_project_crs(self):
        self.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:2193"))
        self.plugin._zoom_to(LINCOLN)
        centre = self.iface.canvas.center()
        # Lincoln in NZTM2000, from an independent transform.
        self.assertAlmostEqual(centre.x(), 1558_000, delta=1500)
        self.assertAlmostEqual(centre.y(), 5168_000, delta=1500)
        self.assertNotAlmostEqual(centre.x(), LINCOLN.lon, places=0)

    def test_zoom_places_marker_and_message(self):
        self.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.plugin._zoom_to(LINCOLN)
        self.assertIsNotNone(self.plugin.marker)
        self.assertAlmostEqual(self.plugin.marker.center().x(), LINCOLN.lon, places=6)
        self.assertEqual(len(self.iface.bar.messages), 1)
        self.assertIn("Lincoln, Canterbury, NZ", self.iface.bar.messages[0][1])
        self.plugin._clear_marker()
        self.assertIsNone(self.plugin.marker)

    def test_gps_source_is_none_without_connections(self):
        self.assertEqual(len(QgsApplication.gpsConnectionRegistry().connectionList()), 0)
        self.assertIsNone(self.plugin._location_from_gps())

    def test_ip_reply_success_zooms(self):
        self.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.plugin.action.setEnabled(False)
        reply = FakeReply(b'{"loc": "-43.64,172.485", "city": "Lincoln", "country": "NZ"}')
        self.plugin._reply = reply
        self.plugin._on_ip_reply()
        self.assertIsNone(self.plugin._reply)
        self.assertTrue(self.plugin.action.isEnabled())
        self.assertTrue(reply.deleted)
        self.assertAlmostEqual(self.iface.canvas.center().x(), 172.485, places=4)
        self.assertIn("Lincoln, NZ", self.iface.bar.messages[-1][1])

    def test_ip_reply_network_error_warns(self):
        reply = FakeReply(error=QNetworkReply.NetworkError.HostNotFoundError,
                          error_string="Host ipinfo.io not found")
        self.plugin._reply = reply
        self.plugin._on_ip_reply()
        self.assertTrue(reply.deleted)
        self.assertIsNone(self.plugin.marker)
        self.assertIn("Host ipinfo.io not found", self.iface.bar.messages[-1][1])

    def test_ip_reply_bogon_warns(self):
        reply = FakeReply(b'{"ip": "10.1.2.3", "bogon": true}')
        self.plugin._reply = reply
        self.plugin._on_ip_reply()
        self.assertIsNone(self.plugin.marker)
        self.assertIn("public IP", self.iface.bar.messages[-1][1])


if __name__ == "__main__":
    unittest.main()
