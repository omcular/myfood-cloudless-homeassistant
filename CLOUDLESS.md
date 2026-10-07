# myfood App Core v0.6.0 — Cloudless Setup & Factory-Image Modifications

A maintained log of the changes needed to run a **myfood** greenhouse controller
"cloudless" — i.e. publishing its own sensor data onto your LAN over MQTT so Home
Assistant (or anything else) can read it locally — while keeping the official cloud
working alongside it.

It doubles as a **post-update checklist**: a myfood security update reflashes the SD
card and wipes every change below, so this is what to re-apply afterwards.

> **Scope / warning.** This is unofficial and was worked out on the owner's own unit by
> observation. It is not endorsed by myfood. Editing `user.json`, poking I²C, and
> changing passwords on your controller can break it or complicate support. Do this only
> on hardware you own. All unit-specific values (IDs, IPs, passwords) are shown as
> `<PLACEHOLDERS>` — fill in your own.

---

## The unit at a glance (v0.6.0)

**Software:** "myfood App Core" — a .NET / ASP.NET Core **Blazor Server** app.
- Admin dashboard: `http://<PI>:5000` (was port **80** on v0.3.2.0).
- Embedded **MQTTnet** broker + publisher (can push readings to a local topic).
- **SQLite** database `myfood.db` (table `Measures`, `SensorTypes`).
- Runs under systemd as **`myfoodapp.core.service`**.
- Pushes readings to the cloud at `hub.myfood.eu` (Azure) when online.
- UI language can be **FR / EN / DE**.

**Hardware (Raspberry Pi 4), I²C bus 1 (`/dev/i2c-1`):**

| Addr   | Device |
|--------|--------|
| `0x40` | ADC / I/O expander |
| `0x51` | **PCF85363A RTC** — battery-backed; the app's time source (see §5) |
| `0x63` | Atlas Scientific EZO **pH** |
| `0x66` | Atlas Scientific EZO **RTD** (water temperature) |
| (others) | EZO EC / ORP / DO as fitted |

Sigfox module on a serial port (`System.IO.Ports`); its `AT_Id` is now the cloud
device identity (see §4). There is **no battery-backed `/dev/rtc`** registered with the
kernel — the app talks to the PCF85363A directly over I²C.

---

## What changed v0.3.2.0 → v0.6.0 (why this doc exists)

- Dashboard port **80 → 5000**.
- The **"Local MQTT server" toggle in the UI does not persist** — flip it on and it
  reverts. Must be set in `user.json` instead (§2).
- **Cloud device identity changed** from a MAC-derived tail to the Sigfox `AT_Id`, so a
  unit registered under the old reference gets cloud **404s** until re-pointed (§4).
- UI may default to **French**; switch it to English or German in the admin settings.

---

## Modifications

Each section: **why**, **how**, and (implicitly) what to redo after a reflash.

### 1. SSH access

The reflashed image has no authorized key for you. Easiest is to add one **offline**:

1. Power off, pull the SD card, mount its **rootfs** partition on your machine.
2. Append your public key to `…/home/pi/.ssh/authorized_keys` (create the `.ssh` dir
   `700` and the file `600`, owned by uid/gid `1000` if you're creating them).
3. Reinsert, boot, `ssh pi@<PI>`.

The `pi` user has **passwordless sudo**. Note that `pi` and `root` also have **default
passwords** on the factory image — change them (§6).

> After a reflash the host key changes; clear the stale entry with
> `ssh-keygen -R <PI>` before reconnecting.

### 2. Enable the local MQTT broker / publishing (`user.json`)

The UI toggle won't stick, so edit the config file directly. It's
`/home/pi/share/myfoodapp.Core/user.json`, owned `root:root`, so back it up and edit it as
root with `nano`:

```bash
cd /home/pi/share/myfoodapp.Core
sudo cp user.json user.json.bak-$(date +%H%M%S)   # back up first
sudo nano user.json
```

It's a flat JSON object — set these keys (change the values, keep the JSON valid):

```json
"mqttEnableLocalServer": true,
"mqttLocalServerUrl": "mqtt://127.0.0.1:1883",
"mqttLocalTopic": "myfood/greenhouse"
```

In `nano`, save with **Ctrl+O** then **Enter**, and exit with **Ctrl+X** (the on-screen
menu may be localized — e.g. French — but the Ctrl shortcuts are the same). Then restart
the app so it picks up the change:

```bash
sudo systemctl restart myfoodapp.core.service
```

The app then publishes one JSON message per measure cycle to the topic. **All values are
strings, and the first message after start has `null` values** (handle that downstream):

```json
{
  "CaptureDate": "2026-10-06T20:39:00+02:00",
  "PhValue": "8.8646",
  "WaterTemperatureValue": "20.058",
  "InternalAirTemperatureValue": "17.8",
  "InternalHumidityValue": "62.0",
  "ExternalAirTemperatureValue": null,
  "ExternalHumidityValue": null
}
```

### 3. Measure frequency

Factory default is **30 min** (`1800000` ms). For more frequent local data, edit the same
file again (`sudo nano user.json`) and set:

```json
"measureFrequency": 300000
```

(5 min.) Restart the service. The cloud doesn't care about this value for local MQTT;
it just controls how often the unit samples and publishes.

### 4. Cloud device identity (fix cloud 404s after an update)

v0.6.0 announces the **Sigfox `AT_Id`** (e.g. shown as `ProdUnitId` on the admin page)
as the device `reference` when pushing to the cloud. If your greenhouse is still
registered under the **old** (MAC-derived) reference, every push returns
*"The specified resource was not found"* (404) and the cloud graphs stop updating.

**Fix (your own cloud account only):** update your greenhouse's stored `reference` to match
the `ProdUnitId`. You do this against the cloud API with the **same credentials as your
myfood web login**. The API is at `https://hub.myfood.eu`, with a browsable Swagger at
`https://hub.myfood.eu/swagger` — use it to confirm the exact request shapes, which can
change between API versions.

**1. Get a bearer token:**

```bash
curl -X POST https://hub.myfood.eu/api/identity/token \
  -H 'Content-Type: application/json' \
  -d '{"userName":"<your-login>","password":"<your-password>"}'
# copy data.token from the response -> use as <TOKEN> below
```

**2. Check the current record** (confirm the mismatch), with your greenhouse id:

```bash
curl -X GET "https://hub.myfood.eu/api/v1/ProductionUnit/GetProductionUnitDetailForUser?id=<GREENHOUSE_ID>" \
  -H "Authorization: Bearer <TOKEN>" -H 'Accept: */*'
```

**3. Patch the reference** to the `ProdUnitId` from the admin page. The endpoint that
updates the owner/unit record is `PatchProductUnitOwnerForUser` — **confirm its exact body
in Swagger**, then send the new `reference`:

```bash
curl -X PATCH "https://hub.myfood.eu/api/v1/ProductionUnit/PatchProductUnitOwnerForUser" \
  -H "Authorization: Bearer <TOKEN>" -H 'Content-Type: application/json' \
  -d '{"id":<GREENHOUSE_ID>,"reference":"<PROD_UNIT_ID>"}'
# success response contains: "Production Unit Updated!"
```

**4. Confirm:** within a measure cycle the controller log should switch from the 404 to
*"Measures sent to Azure via Internet"*, and the cloud dashboard resumes updating.

Your login and ids are account-specific — fill in your own; nothing here is published.

### 5. Clock / RTC (PCF85363A) — the sneaky one

**The app does not use the OS clock or NTP for timestamps.** It reads a battery-backed
**PCF85363A RTC at `0x51`** directly over I²C (its "Clock Service"). If that chip holds
the wrong time — e.g. it got set during a boot before NTP corrected the OS clock — then
**every `CaptureDate` (MQTT, cloud, and the on-device graphs) is wrong**, even while
`date`/`timedatectl` on the Pi look perfectly correct. Restarting the service does **not**
resync it.

The chip stores **UTC**; the app adds your timezone offset for display.

**Fix options (any one):**

- **Admin web UI** — set the date/time in the controller's settings. Simplest; this
  writes the RTC the app's own way. (Set time and date carefully; the field can be
  finicky.)
- **Kernel driver + `hwclock`** (the chip isn't bound by default, so make the kernel
  adopt it, write, then release it so the app keeps sole access):
  ```bash
  sudo systemctl stop myfoodapp.core.service
  sudo modprobe rtc-pcf85363
  echo pcf85363 0x51 | sudo tee /sys/bus/i2c/devices/i2c-1/new_device   # -> /dev/rtc0
  sudo hwclock -w --utc --rtc /dev/rtc0        # system(UTC) -> chip
  sudo hwclock -r --rtc /dev/rtc0              # read back; compare to `date -u`
  echo 0x51 | sudo tee /sys/bus/i2c/devices/i2c-1/delete_device
  sudo systemctl start myfoodapp.core.service
  ```
- **Raw `i2cset`** — PCF85363A time registers are BCD: `0x00` 1/100s, `0x01` sec,
  `0x02` min, `0x03` hour (24h), `0x04` day, `0x05` weekday, `0x06` month, `0x07` year.
  Set the STOP bit (`0x2E`=`0x01`) and clear the prescaler (`0x2F`=`0xA4`) before writing,
  clear STOP (`0x2E`=`0x00`) after. (Fiddliest; prefer one of the above.)

**Verify:** the app log line `Clock Service read value : Year … Day … Hours …` should
show real UTC, and new `Measures.captureDate` rows should be current. Log dir:
`/home/pi/share/myfoodapp.Core/Logs/<yyyy>/<MM>/trace-*.log`.

### 6. Hardening (do this)

The factory image ships with **guessable default passwords** for `pi`/`root` and a
**default Wi-Fi AP key**. Together those mean anyone within Wi-Fi range can join the AP
and get a shell. On your own unit:

- `passwd` and `sudo passwd root` — set strong, unique passwords.
- Change the **Wi-Fi AP password** in the controller/OS config.
- At the network layer, scope access: allow only your **HA host → `<PI>:1883`** (MQTT)
  and your admin workstation → `:22`/`:5000`; block the rest.
- Keep SSH key-based; consider disabling password auth once your key works.

Default credentials are deliberately **not** reproduced here. If you're looking at the
fleet rather than your own unit, the responsible path is coordinated disclosure to myfood
— not publishing defaults or unit locations.

---

## Home Assistant side

### Mosquitto bridge (HA add-on)

HA's Mosquitto add-on bridges the Pi's embedded broker into HA's broker. Requires the
add-on's `customize: active: true, folder: mosquitto`, then create
`/share/mosquitto/myfood_bridge.conf`:

```
connection myfoodpi
address <PI>:1883
topic myfood/# in 0
remote_clientid ha-myfood-bridge
try_private false
cleansession true
start_type automatic
notifications false
```

> **`try_private false` is critical.** With the default `true`, non-Mosquitto brokers
> (the app's MQTTnet) reject the bridge. The bridge auto-reconnects when the Pi service
> restarts.

### MQTT sensors

The payload isn't HA MQTT-discovery format, so define the entities explicitly. See
[`examples/homeassistant-mqtt.yaml`](examples/homeassistant-mqtt.yaml): four sensors on
topic `myfood/greenhouse` with an `availability` block that marks them unavailable when a
value is `null` (so the null first-message doesn't clobber the last good reading). Add the
`mqtt:` block to `configuration.yaml` (only one top-level `mqtt:` key allowed), then
Developer Tools → YAML → **"Manually configured MQTT entities" → Reload**.

---

## After a firmware update — re-apply checklist

A security update reflashes the card and wipes everything above.

1. **SSH key** — offline SD-card mount (§1). Clear old host key: `ssh-keygen -R <PI>`.
2. **Harden** — `pi`/`root` passwords + AP key (§6).
3. **MQTT + cadence** — set `mqttEnableLocalServer`, `mqttLocalTopic`, `measureFrequency`
   in `user.json`; restart the service (§2, §3).
4. **Cloud** — check `ProdUnitId` on the admin page; if cloud pushes 404, re-point the
   greenhouse `reference` (§4).
5. **Clock** — verify the RTC reads real time; fix via admin UI if not (§5).
6. **HA** — the bridge reconnects on its own; confirm the four entities repopulate.

---

## Pi file reference

| Path | What |
|------|------|
| `/home/pi/share/myfoodapp.Core/user.json` | MQTT + cadence + identity config (`root:root`) |
| `/home/pi/share/myfoodapp.Core/unit.json` | Sigfox `AT_Id` / `AT_Pac` |
| `/home/pi/share/myfoodapp.Core/myfood.db` | SQLite: `Measures`, `SensorTypes` |
| `/home/pi/share/myfoodapp.Core/Logs/<y>/<m>/trace-*.log` | App log (Clock Service, MQTT, cloud) |
| `myfoodapp.core.service` (systemd) | The app; `systemctl restart` to apply config |

`SensorTypes`: `1`=pH, `2`=waterTemperature, `3`=dissolvedO2, `4`=EC,
`5`=airTemperature, `6`=ORP.

---

## Disclaimer

Not affiliated with or endorsed by myfood. Determined by observing the owner's own
device. Use on equipment you own.
