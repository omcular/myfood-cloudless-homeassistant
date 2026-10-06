# myfood-cloudless

Read your [myfood](https://myfood.eu) greenhouse's sensors **locally**, straight from
the controller on your LAN. No cloud account, no API token, no credentials.

Provides pH, water temperature, air temperature, and humidity, ready to wire into
Home Assistant.

## Why

The official path reads sensor data from myfood's cloud API, which means depending on
their servers, storing a bearer token, and (with the common Home Assistant REST setup)
leaking that token into HA's state history. This project reads the same values directly
from the controller instead:

- **No credentials.** The controller's local dashboard is unauthenticated.
- **No cloud.** Works even if myfood's servers or your internet are down.
- **Nothing sensitive stored.** There is no token to leak.

## How it works

The modern myfood controller ("myfood App Core") is an ASP.NET Core **Blazor Server**
app. It renders the dashboard on the Pi and streams UI updates to the browser over a
SignalR circuit (`/_blazor`); there is **no local REST/JSON API** to call.

So this tool speaks that protocol directly:

1. `GET /` to collect the page's fresh, signed Blazor component descriptors.
2. `POST /_blazor/negotiate` to open a SignalR connection (Long Polling transport).
3. Send the handshake, then a `StartCircuit` invocation (MessagePack) carrying those
   descriptors.
4. Receive the first render batch and extract the four values from it.
5. Close the circuit cleanly.

It is, in effect, a tiny headless Blazor client. See `docs/` for the wire-level detail.

## Requirements

- Python 3.8+ (standard library only, no dependencies).
- Network reachability from wherever you run it to the controller on your LAN.

## Usage

```bash
# If your network resolves the device name:
python3 -m myfood_cloudless.reader --host myfoodpi

# Or connect by IP and pass the device name as the HTTP Host header:
python3 myfood_cloudless/reader.py --host 192.168.8.221 --vhost myfoodpi
```

Output is one line of JSON:

```json
{"ph": 8.2, "water_temp": 15.7, "air_temp": 16.2, "humidity": 66.0, "last_sample": "10:13 AM", "ts": 1700000000}
```

`last_sample` is the controller's own timestamp for the most recent reading (local
time, coarse). `ts` is when this fetch ran.

Configuration can also come from the environment: `MYFOOD_HOST`, `MYFOOD_VHOST`,
`MYFOOD_PORT`.

## Home Assistant

The controller samples roughly **every 30 minutes**. Either method below polls every
60 s for low latency; HA's recorder only writes a row when a value actually changes, so
stored data stays at ~30-minute granularity regardless of poll rate.

### Option A — custom integration (recommended)

Copy `custom_components/myfood_cloudless/` into your HA `config/custom_components/`
directory and restart Home Assistant. Then go to **Settings -> Devices & Services ->
Add Integration**, search for **myfood cloudless**, and enter your controller's host
(e.g. `myfoodpi`, or an IP with the device name in the advanced *Host header* field).

You get one **myfood Greenhouse** device with four sensor entities (pH, water
temperature, air temperature, humidity), set up entirely from the UI. Home Assistant
must be able to reach the controller on the LAN; the setup dialog reports a connection
error if it cannot.

### Option B — command_line sensor (no custom component)

See [`examples/configuration.yaml`](examples/configuration.yaml): drop `reader.py` on
the HA host and add a `command_line` sensor that runs it plus four `template` sensors.

## Limitations

- **~30-minute update cadence.** That is how often the controller takes a reading;
  polling faster just returns the same value until the next sample.
- **Fragile by nature.** This parses rendered UI text, not a stable API. A myfood app
  update could change the layout and break the parser; then the regex in `reader.py`
  needs updating.
- **Tested against** "myfood App Core" v0.3.2.0 on a Family22 unit. Other versions may
  differ.

## Roadmap

- [ ] Package as a proper Home Assistant custom integration (config flow + HACS) so it
      installs from the UI instead of a `command_line` sensor.
- [ ] Optional cloud fallback for exact UTC capture timestamps.

## Disclaimer

Not affiliated with or endorsed by myfood. The local protocol was determined by
observing an ordinary browser session against the owner's own device. Use on equipment
you own.

## License

MIT © Om Cular. See [`LICENSE`](LICENSE).
