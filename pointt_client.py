"""Bosch Pointt REST API client (replaces the dead XMPP+AES approach).

Firmware 05.04.00 devices no longer speak XMPP/AES at all -- the official
app talks to a plain REST API secured by OAuth2 (SingleKey ID), discovered
via mitmproxy. This mints a fresh access token from the stored refresh
token and calls the REST API directly.
"""
import json
import requests

CRED_FILE = "pointt_credentials.json"
TOKEN_URL = "https://singlekey-id.com/auth/connect/token"
API_BASE = "https://pointt-api.bosch-thermotechnology.com/pointt-api/api/v1"


def load_creds():
    with open(CRED_FILE) as f:
        return json.load(f)


def save_creds(creds):
    with open(CRED_FILE, "w") as f:
        json.dump(creds, f, indent=2)


def refresh_access_token():
    creds = load_creds()
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    tokens = resp.json()
    # Duende IdentityServer rotates refresh tokens on use -- persist the new one.
    if tokens.get("refresh_token"):
        creds["refresh_token"] = tokens["refresh_token"]
        save_creds(creds)
    return tokens["access_token"]


def get_gateways(access_token):
    resp = requests.get(
        f"{API_BASE}/gateways",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_resource(access_token, device_id, path):
    resp = requests.get(
        f"{API_BASE}/gateways/{device_id}/resource/{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def put_resource(access_token, device_id, path, value):
    resp = requests.put(
        f"{API_BASE}/gateways/{device_id}/resource/{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"value": value},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.status_code


if __name__ == "__main__":
    token = refresh_access_token()
    print("Got fresh access token.")

    gateways = get_gateways(token)
    print("Gateways:", gateways)

    device_id = gateways[0]["deviceId"]

    for path in (
        "zones/zn1/temperatureActual",
        "zones/zn1/temperatureHeatingSetpoint",
        "zones/zn1/userMode",
        "system/info",
    ):
        value = get_resource(token, device_id, path)
        print(f"{path}: {value}")
