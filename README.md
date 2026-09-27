# HiChip Floodlight for Home Assistant

Local control of the built‑in floodlight on **GF‑L300 / HiChip “IOTLiving”**
cameras — the ones with no relay, no ONVIF light command and no local web
control for the lamp. This integration talks to the camera directly on your LAN
over its native **PPPP** protocol, so it needs **no cloud and no app running**.

It adds a `switch` entity for the floodlight (on / off) plus an `auto` mode.

## How it works

The floodlight can normally only be toggled from the IOTLiving phone app, which
uses an encrypted peer‑to‑peer protocol. This integration establishes the same
LAN session the app does, replays the (device‑specific, deterministic) login and
485‑light‑module setup, and sends the on/off/auto command. The camera returns a
success ack, exactly as it does for the app.

Because the camera exposes no *readable* light state locally, the switch tracks
the last command it sent (optimistic state) — the same way most local‑push
switches behave.

## Installation (HACS)

1. HACS -> the three-dot menu -> **Custom repositories** -> add
   `https://github.com/denveronly/ha-hichip-floodlight`, category **Integration**.
2. Install **HiChip Floodlight**, then restart Home Assistant.
3. **Create your device profile file** (see below) at
   `/config/hichip_floodlight_profile.json`.
4. **Settings -> Devices & services -> Add integration -> HiChip Floodlight**,
   enter a name and the camera IP.

## Device profile (`hichip_floodlight_profile.json`)

The login and command payloads are **per-device** and act as a
password-equivalent token, so they are **not** committed to this repo. You keep
them in a local file only your Home Assistant can read:

```
/config/hichip_floodlight_profile.json
```

See `profile.example.json` for the shape. The payloads are captured from one
authenticated session of the vendor app on your own LAN; they stay valid until
the camera password changes.

## Limitations

- One camera per profile file; arbitrary-password/multi-camera support would
  require reproducing the vendor's key derivation, which is not implemented.
- No live state read‑back (optimistic state only).
- LAN only — the camera and Home Assistant must be on the same network.

## Credits

Reverse‑engineered for local interoperability with hardware the owner controls.
Not affiliated with HiChip or the IOTLiving app.
