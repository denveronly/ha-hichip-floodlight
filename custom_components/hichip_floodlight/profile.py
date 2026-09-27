"""Loads the per-device camera profile from the Home Assistant config dir.

The profile (UID + login/command payloads) is device-specific and acts as a
password-equivalent token, so it is NOT bundled in this public repository.
Place your own profile at:  <config>/hichip_floodlight_profile.json
(see profile.example.json in the repo for the shape).
"""
from __future__ import annotations

import json
import os

PROFILE_FILENAME = "hichip_floodlight_profile.json"
REQUIRED = ("uid", "setup", "cmd_on", "cmd_off", "cmd_auto")


class ProfileError(Exception):
    """Profile file missing or malformed."""


def load_profile(config_dir: str) -> dict:
    path = os.path.join(config_dir, PROFILE_FILENAME)
    if not os.path.exists(path):
        raise ProfileError(
            f"{PROFILE_FILENAME} not found in {config_dir}. Create it "
            "(see profile.example.json)."
        )
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ProfileError(f"{PROFILE_FILENAME} missing keys: {missing}")
    return data
