from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error

TOKENS_PATH = Path("~/.config/tagslut/tokens.json").expanduser()

class BeatportAuthManager:
    def __init__(self, tokens_path: Path = TOKENS_PATH) -> None:
        self.tokens_path = tokens_path

    def get_dj_token(self) -> str | None:
        """Retrieves the Beatport DJ token from tokens.json or environment variables."""
        # First check environment variable
        token = os.environ.get("BEATPORT_DJ_TOKEN")
        if token:
            return token

        # Fallback to local config file
        if self.tokens_path.exists():
            try:
                data = json.loads(self.tokens_path.read_text(encoding="utf-8"))
                # Support different formats of tokens.json
                if isinstance(data, dict):
                    # Check for nested beatport key
                    bp_data = data.get("beatport")
                    if isinstance(bp_data, dict):
                        token = bp_data.get("access_token") or bp_data.get("dj_token") or bp_data.get("token")
                        if token:
                            return token
                    return data.get("access_token") or data.get("dj_token") or data.get("token")
            except Exception:
                pass
        return None

    def get_v4_credentials(self) -> dict[str, str] | None:
        """Retrieves Beatport v4 Client Credentials from environment variables."""
        client_id = os.environ.get("BEATPORT_CLIENT_ID")
        client_secret = os.environ.get("BEATPORT_CLIENT_SECRET")
        if client_id and client_secret:
            return {"client_id": client_id, "client_secret": client_secret}
        return None

    def fetch_v4_token(self) -> str | None:
        """Obtains a Bearer token using the v4 Client Credentials flow."""
        creds = self.get_v4_credentials()
        if not creds:
            return None

        url = "https://api.beatport.com/v4/oauth/token/"
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"]
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        try:
            with urllib.request.urlopen(req) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("access_token")
        except Exception:
            return None
