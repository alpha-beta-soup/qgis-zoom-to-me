# Zoom to Me

A QGIS plugin that adds one toolbar button: zoom the map to where this computer
appears to be.

It tries two sources in order:

1. **A live GPS connection in QGIS.** If you have connected a receiver through
   the GPS panel, the most recent fix is used and the map zooms close, scaled by
   the reported horizontal accuracy when the receiver provides one.
2. **Your public IP address**, looked up at <https://ipinfo.io>. This is
   accurate to about the city at best, and will be wrong behind a VPN or a
   corporate gateway that exits somewhere else.

After zooming, a red circle marks the point for a few seconds and the message
bar says which source was used.

Privacy: the fallback sends your public IP address to ipinfo.io, a third-party
service. Nothing else is sent. If a GPS fix is available no network request is
made.

## Install for development

```sh
make deploy        # copies the plugin into the default QGIS profile
```

Then enable "Zoom to Me" in Plugins > Manage and Install Plugins. The
[Plugin Reloader](https://plugins.qgis.org/plugins/plugin_reloader/) plugin
makes iterating easier.

Set `QGIS_PLUGIN_DIR` if your profile lives somewhere else:

```sh
make deploy QGIS_PLUGIN_DIR=~/.local/share/QGIS/QGIS3/profiles/work/python/plugins
```

## Tests

The parsing and scale logic has no QGIS dependency:

```sh
make test
```

## Package

```sh
make zip           # writes dist/zoom_to_me.zip for plugins.qgis.org
```
