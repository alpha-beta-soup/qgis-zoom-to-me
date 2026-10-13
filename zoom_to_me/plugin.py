"""QGIS-facing part of Zoom to Me: one toolbar button that centres the map on
where this machine appears to be."""

import math
import os

from qgis.PyQt.QtCore import QTimer, QUrl
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsNetworkAccessManager,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)
from qgis.gui import QgsVertexMarker

from .location import IPINFO_URL, Location, Source

TITLE = "Zoom to me"
REQUEST_TIMEOUT_MS = 8000
MARKER_LIFETIME_MS = 15000


class ZoomToMePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.marker = None
        self._reply = None
        self._marker_timer = QTimer()
        self._marker_timer.setSingleShot(True)
        self._marker_timer.timeout.connect(self._clear_marker)

    # QGIS plugin interface -------------------------------------------------

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, TITLE, self.iface.mainWindow())
        self.action.setToolTip("Zoom the map to where this computer appears to be")
        self.action.setStatusTip(
            "Uses a connected GPS if QGIS has one, otherwise looks up your IP address"
        )
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(TITLE, self.action)

    def unload(self):
        self._clear_marker()
        self._marker_timer.stop()
        if self._reply is not None:
            self._reply.abort()
            self._reply = None
        if self.action is not None:
            self.iface.removePluginMenu(TITLE, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    # Behaviour -------------------------------------------------------------

    def run(self):
        self._clear_marker()
        location = self._location_from_gps()
        if location is not None:
            self._zoom_to(location)
            return
        self._locate_by_ip()

    def _location_from_gps(self):
        """Return a Location from any live QGIS GPS connection, or None."""
        registry = QgsApplication.gpsConnectionRegistry()
        for conn in registry.connectionList():
            info = conn.currentGPSInformation()
            # isValid() alone is not enough: a freshly constructed, empty
            # QgsGpsInformation reports valid. Require an actual 2D/3D fix.
            has_fix = info.fixType in (2, 3) or info.quality > 0
            if not (info.isValid() and has_fix):
                continue
            hacc = getattr(info, "hacc", float("nan"))
            accuracy = hacc if (isinstance(hacc, float) and math.isfinite(hacc) and hacc > 0) else None
            return Location(
                lon=info.longitude,
                lat=info.latitude,
                source=Source.GPS,
                label="GPS fix",
                accuracy_m=accuracy,
            )
        return None

    def _locate_by_ip(self):
        if self._reply is not None:
            return  # a lookup is already in flight
        request = QNetworkRequest(QUrl(IPINFO_URL))
        request.setRawHeader(b"Accept", b"application/json")
        if hasattr(request, "setTransferTimeout"):
            request.setTransferTimeout(REQUEST_TIMEOUT_MS)
        self.action.setEnabled(False)
        self.iface.messageBar().pushMessage(
            TITLE, "No GPS fix, asking ipinfo.io where this IP address is...",
            level=Qgis.MessageLevel.Info, duration=3,
        )
        self._reply = QgsNetworkAccessManager.instance().get(request)
        self._reply.finished.connect(self._on_ip_reply)

    def _on_ip_reply(self):
        reply, self._reply = self._reply, None
        if self.action is not None:
            self.action.setEnabled(True)
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._warn(f"Could not reach ipinfo.io: {reply.errorString()}")
                return
            try:
                from .location import parse_ipinfo
                location = parse_ipinfo(bytes(reply.readAll()))
            except ValueError as exc:
                self._warn(str(exc))
                return
        finally:
            reply.deleteLater()
        self._zoom_to(location)

    def _zoom_to(self, location: Location):
        canvas = self.iface.mapCanvas()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        dest = canvas.mapSettings().destinationCrs()
        point = QgsPointXY(location.lon, location.lat)
        if dest.isValid() and dest != wgs84:
            transform = QgsCoordinateTransform(wgs84, dest, QgsProject.instance())
            try:
                point = transform.transform(point)
            except Exception as exc:  # QgsCsException
                self._warn(f"Could not transform the location into the project CRS: {exc}")
                return

        if canvas.extent().isEmpty():
            # setCenter/zoomScale are no-ops on a canvas with a null extent
            # (e.g. a new project with no layers), so seed one first.
            canvas.setExtent(QgsRectangle(point.x() - 1, point.y() - 1, point.x() + 1, point.y() + 1))
        canvas.setCenter(point)
        canvas.zoomScale(location.scale())
        canvas.refresh()

        self.marker = QgsVertexMarker(canvas)
        self.marker.setCenter(point)
        self.marker.setIconType(QgsVertexMarker.IconType.ICON_CIRCLE)
        self.marker.setColor(QColor(220, 40, 40))
        self.marker.setFillColor(QColor(220, 40, 40, 60))
        self.marker.setIconSize(18)
        self.marker.setPenWidth(3)
        self._marker_timer.start(MARKER_LIFETIME_MS)

        self.iface.messageBar().pushMessage(
            TITLE, location.describe(), level=Qgis.MessageLevel.Info, duration=8
        )

    def _clear_marker(self):
        if self.marker is not None:
            canvas = self.iface.mapCanvas()
            canvas.scene().removeItem(self.marker)
            self.marker = None
            canvas.refresh()

    def _warn(self, text: str):
        self.iface.messageBar().pushMessage(
            TITLE, text, level=Qgis.MessageLevel.Warning, duration=10
        )
