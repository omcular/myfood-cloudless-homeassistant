#!/usr/bin/env python3
"""myfood-cloudless: read a myfood greenhouse's sensors from the controller on your
LAN, with no cloud account and no credentials.

The modern myfood controller ("myfood App Core", Blazor Server) exposes no local
REST API. Its dashboard is rendered on the Pi and streamed to the browser over a
SignalR circuit (/_blazor). This tool speaks that protocol: it loads the page for
fresh signed component descriptors, negotiates the circuit, sends StartCircuit,
receives the first render batch, and parses the four values out of it.

Output (stdout, one line of JSON):
    {"ph": 8.2, "water_temp": 15.7, "air_temp": 16.2, "humidity": 66.0,
     "last_sample": "10:13 AM", "ts": 1700000000}

Usage:
    python3 -m myfood_cloudless.reader --host myfoodpi
    python3 reader.py --host 192.168.8.221 --vhost myfoodpi   # connect by IP

Config may also come from env: MYFOOD_HOST, MYFOOD_VHOST, MYFOOD_PORT.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.parse


def _mp_str(s):
    b = s.encode(); n = len(b)
    if n < 32:    return bytes([0xa0 | n]) + b
    if n < 256:   return bytes([0xd9, n]) + b
    if n < 65536: return bytes([0xda, n >> 8, n & 255]) + b
    return bytes([0xdb, (n >> 24) & 255, (n >> 16) & 255, (n >> 8) & 255, n & 255]) + b


def _leb(n):
    o = bytearray()
    while True:
        x = n & 0x7f; n >>= 7; o.append(x | (0x80 if n else 0))
        if not n:
            return bytes(o)


class Reader:
    def __init__(self, host, vhost=None, port=80, timeout=20):
        self.addr = f"{host}:{port}" if port != 80 else host
        self.vhost = vhost or host
        self.base = f"http://{self.vhost}/"
        self.timeout = timeout

    def _req(self, path, method="GET", data=None, timeout=None):
        r = urllib.request.Request(f"http://{self.addr}{path}", method=method, data=data)
        r.add_header("Host", self.vhost)
        if data is not None:
            r.add_header("Content-Type", "text/plain;charset=UTF-8")
        with urllib.request.urlopen(r, timeout=timeout or self.timeout) as resp:
            return resp.read()

    def read(self):
        html = self._req("/").decode("utf-8", "replace")
        srv = [json.loads(m) for m in re.findall(r'<!--Blazor:(\{.*?\})-->', html, re.S)
               if '"descriptor"' in m]
        if not srv:
            raise RuntimeError("no Blazor component descriptors on page; is this a myfood App Core host?")
        for i, o in enumerate(srv):
            o["uniqueId"] = i
        arg3 = json.dumps(srv, separators=(",", ":"), ensure_ascii=False)

        tok = json.loads(self._req("/_blazor/negotiate?negotiateVersion=1", "POST", b""))["connectionToken"]
        qid = urllib.parse.quote(tok)
        poll = lambda: self._req(f"/_blazor?id={qid}&_={int(time.time()*1000)}")
        send = lambda p: self._req(f"/_blazor?id={qid}", "POST", p)

        poll()
        send(b'{"protocol":"blazorpack","version":1}\x1e')
        poll()
        args = bytes([0x94]) + _mp_str(self.base) + _mp_str(self.base) + _mp_str(arg3) + _mp_str("")
        payload = bytes([0x95, 0x01, 0x80]) + _mp_str("0") + _mp_str("StartCircuit") + args
        send(_leb(len(payload)) + payload)

        # Metric keywords across the UI's three languages (FR / EN / DE). The nearest
        # term to a value wins, so "Air Humidity"/"Luftfeuchtigkeit" map to humidity
        # rather than air. pH is matched case-sensitively so it never hits CSS ("typography").
        metric_terms = {
            "humidity": ("humid", "feucht"),          # Humidité / Humidity / Luftfeuchtigkeit
            "water_temp": ("eau", "water", "wasser"),  # l'eau / Water / Wassertemperatur
            "air_temp": ("air", "luft"),               # l'air / Air / Lufttemperatur
        }
        blob = b""
        try:
            for _ in range(10):
                try:
                    blob += poll()
                except Exception:
                    pass
                lat = blob.decode("latin-1")
                out = {}
                # Language-independent anchor: the " : " fragment (a 3-char string, so
                # length-prefixed by \x03) that sits just before each value, rather than
                # the localized word "mesure"/"Messung".
                for m in re.finditer(r'\x03 : .([0-9]+(?:[.,][0-9]+)?)', lat):
                    back = lat[max(0, m.start() - 60):m.start()]
                    low = back.lower()
                    cand = {name: max((low.rfind(t) for t in terms), default=-1)
                            for name, terms in metric_terms.items()}
                    cand["ph"] = back.rfind("pH")
                    metric = max(cand, key=cand.get)
                    if cand[metric] >= 0:
                        out[metric] = float(m.group(1).replace(",", "."))
                if len(out) >= 4:
                    times = re.findall(r'\d{1,2}:\d{2}\s?[AP]M', lat)
                    if times:
                        out["last_sample"] = times[-1]
                    out["ts"] = int(time.time())
                    return out
            raise RuntimeError("timed out before all four values arrived; got " + json.dumps(out))
        finally:
            try:
                self._req(f"/_blazor?id={qid}", method="DELETE", timeout=5)
            except Exception:
                pass


def main(argv=None):
    p = argparse.ArgumentParser(description="Read myfood greenhouse sensors locally (no cloud).")
    p.add_argument("--host", default=os.environ.get("MYFOOD_HOST", "myfoodpi"),
                   help="controller hostname or IP to connect to (default: myfoodpi)")
    p.add_argument("--vhost", default=os.environ.get("MYFOOD_VHOST"),
                   help="HTTP Host header / base URI host (default: same as --host; "
                        "set to the device name when connecting by IP)")
    p.add_argument("--port", type=int, default=int(os.environ.get("MYFOOD_PORT", "80")))
    p.add_argument("--timeout", type=int, default=20)
    a = p.parse_args(argv)
    try:
        print(json.dumps(Reader(a.host, a.vhost, a.port, a.timeout).read()))
        return 0
    except Exception as e:
        print(f"myfood-cloudless: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
