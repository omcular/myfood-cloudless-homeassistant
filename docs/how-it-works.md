# Wire-level notes

The controller serves a Blazor Server app on port 80 (another instance on 5000).
Port 8080 is unrelated (RaspAP / lighttpd, the device's Wi-Fi access-point manager).

## Transport

The browser tries a WebSocket to `/_blazor` and falls back to **SignalR Long Polling**:
paired `GET`/`POST /_blazor?id=<connectionToken>` requests. `GET` receives server->client
frames; `POST` sends client->server frames.

## Sequence

1. `GET /` — the HTML contains two `<!--Blazor:{...}-->` server-component markers, each
   with a `descriptor` (an ASP.NET Data Protection blob) that is regenerated per page
   load. These must be fresh; stale ones are rejected.
2. `POST /_blazor/negotiate?negotiateVersion=1` -> JSON with a `connectionToken`.
3. `GET /_blazor?id=<token>` — establish the poll.
4. `POST /_blazor?id=<token>` body `{"protocol":"blazorpack","version":1}\x1e` — handshake.
5. `POST /_blazor?id=<token>` — the `StartCircuit` invocation, MessagePack:
   `[1, {}, "0", "StartCircuit", [baseUri, baseUri, descriptorsJson, ""]]`, prefixed with
   a LEB128 length. `descriptorsJson` is the array of the two markers, each with
   `"uniqueId": <index>` appended.
6. `GET /_blazor?id=<token>` (repeat) — the server sends render batches; the large first
   batch (~57 KB here) carries the dashboard.
7. `DELETE /_blazor?id=<token>` — close.

## Parsing the values

Render-batch text is a UTF-8 string table with length prefixes between fragments, so the
label and value are not contiguous. Each reading appears as:

```
...mesure \x03 " : " <len> <value> ...
```

i.e. the literal `mesure`, a `\x03` (length of the `" : "` fragment), `" : "`, a length
byte, then the numeric value. The regex `mesure\x03 : .([0-9]+(?:[.,][0-9]+)?)` captures
it; the metric is identified by the nearest preceding keyword (`pH`, `l'eau`, `l'air`,
`Humidit`).
