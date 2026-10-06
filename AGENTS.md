# AGENTS.md

Guidance for AI coding agents and human contributors working in this repo.

## What this project is

A local, credential-free reader for myfood greenhouses, plus a Home Assistant custom
integration built on it. The controller ("myfood App Core") is a Blazor Server app with
**no local REST API**; the data is only available over its SignalR circuit. We speak
that protocol and parse the rendered values out. See `README.md` for the overview and
`docs/how-it-works.md` for the wire-level detail.

## Layout

```
myfood_cloudless/reader.py                      # the core Blazor client + CLI (source of truth)
custom_components/myfood_cloudless/             # Home Assistant integration
  reader.py                                     # COPY of the core reader (see "Keep in sync")
  __init__.py  coordinator.py  sensor.py  config_flow.py  const.py
  manifest.json  strings.json  translations/en.json
examples/configuration.yaml                     # command_line + template alternative
docs/how-it-works.md                            # protocol + parser notes
```

## Core invariants

- **No third-party dependencies.** `reader.py` uses the Python standard library only
  (`urllib`, `re`, `json`, ...). The HA `manifest.json` has `"requirements": []`. Keep it
  that way; do not add packages.
- **Keep the two `reader.py` files in sync.** `custom_components/myfood_cloudless/reader.py`
  is a verbatim copy of `myfood_cloudless/reader.py`, so the integration is self-contained
  for HACS. Change the core file, then copy it over:
  `cp myfood_cloudless/reader.py custom_components/myfood_cloudless/reader.py`.
- **The parser is the fragile part.** Values are pulled from Blazor render-batch text with
  the regex `mesure\x03 : .([0-9]+(?:[.,][0-9]+)?)`, mapped to a metric by the nearest
  preceding keyword (`pH`, `l'eau`, `l'air`, `Humidit`). A myfood app update can change the
  rendered text or framing; if readings stop parsing, re-capture a render batch and adjust
  the regex in `reader.py`. Do not change the output JSON keys (`ph`, `water_temp`,
  `air_temp`, `humidity`, `last_sample`, `ts`) without updating `const.py` and `sensor.py`.

## Home Assistant specifics

- Target is current HA (Python 3.14 builds at time of writing). Import `DeviceInfo` from
  `homeassistant.helpers.entity`, **not** `homeassistant.helpers.device_info` (absent on
  current HA).
- The integration is a standard coordinator + config-flow pattern: `MyfoodCoordinator`
  (`DataUpdateCoordinator`, 60 s) runs the blocking `Reader.read` via
  `hass.async_add_executor_job`; `config_flow.py` validates with a test read and returns
  `cannot_connect` on failure.
- The reader connects by host/IP and sends a `Host` header (`--vhost`). When HA is on a
  different subnet than the controller, use the IP as host and the device name as vhost,
  and ensure HA can route to the controller.

## Testing / verification

- Syntax: `python3 -m py_compile custom_components/myfood_cloudless/*.py myfood_cloudless/*.py`.
- Live read (needs LAN access to a controller):
  `python3 -m myfood_cloudless.reader --host <ip> --vhost myfoodpi`
  Expect one JSON line with the four values. The controller samples ~every 30 minutes,
  so values only change that often.
- HA deploy: copy `custom_components/myfood_cloudless/` to `<config>/custom_components/`
  and restart Home Assistant Core (a "Quick reload" will not load new integration code).

## Do not commit

Personal and captured data stay out of the repo and are covered by `.gitignore`:
credentials (`secrets.yaml`), HAR captures (`*.har`), screenshots (`*.png`/`*.jpg`).
Never add real tokens, account details, or greenhouse identifiers to tracked files.

## Style

4-space indentation, type hints on new HA code, keep modules small and single-purpose,
and prefer editing the existing files over adding new ones.
