"""One-time login helper for the Bosch Pointt API.

Does the OAuth2 authorization_code + PKCE flow the real app uses, but lets
you log in through your own real browser (so SingleKey ID's hCaptcha is
solved by you, normally -- nothing here tries to script past it). Only the
final code-for-tokens exchange is automated.

Usage:
    venv/Scripts/python.exe pointt_login.py

Follow the printed instructions, paste the redirect URL when asked, and it
writes a fresh refresh_token to pointt_credentials.json.
"""
import base64
import hashlib
import secrets
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests

CLIENT_ID = "BEAE0439-49D3-41B5-83D1-59B0971793F4"
REDIRECT_URI = "com.bosch.rrc://app/oidc_redirect"
AUTHORIZE_URL = "https://singlekey-id.com/auth/connect/authorize"
TOKEN_URL = "https://singlekey-id.com/auth/connect/token"
SCOPE = (
    "email profile openid offline_access phone "
    "pointt.gateway.claiming pointt.gateway.removal pointt.gateway.list "
    "pointt.gateway.users pointt.gateway.resource.rrcng.app "
    "pointt.castt.flow.token-exchange"
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main():
    code_verifier = b64url(secrets.token_bytes(32))
    code_challenge = b64url(hashlib.sha256(code_verifier.encode()).digest())
    state = b64url(secrets.token_bytes(16))
    nonce = b64url(secrets.token_bytes(16))

    params = {
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "response_type": "code",
        "prompt": "login",
        "state": state,
        "nonce": nonce,
        "scope": SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "style_id": "tt_bsch",
    }
    url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    print("Opening SingleKey ID login in your browser...")
    print("(If it doesn't open, paste this URL manually:)")
    print(url)
    print()
    webbrowser.open(url)

    print("Log in with your Bosch/SingleKey ID account (solve the captcha normally).")
    print("After a successful login, the browser will try to navigate to a")
    print(f'"{REDIRECT_URI}" link and fail (no app can handle it) -- that\'s expected.')
    print("Open DevTools (F12) > Network tab, find that failed request, and copy")
    print("its full URL. Or check the address bar / browser history for it.")
    print()
    print("SECURITY: that URL contains a short-lived one-time authorization code.")
    print("Don't share it, log it, or post it anywhere -- paste it here only.")
    print()
    redirect_url = input("Paste the full redirect URL here: ").strip()

    parsed = parse_qs(urlparse(redirect_url).query)
    if "code" not in parsed:
        print("No 'code' parameter found in that URL -- did you paste the right one?")
        return
    if parsed.get("state", [None])[0] != state:
        print("WARNING: state mismatch -- this doesn't look like a response to the")
        print("request we just made. Aborting rather than risk using a stale/wrong code.")
        return

    code = parsed["code"][0]

    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": CLIENT_ID,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    tokens = resp.json()

    import json

    with open("pointt_credentials.json", "w") as f:
        json.dump({"client_id": CLIENT_ID, "refresh_token": tokens["refresh_token"]}, f, indent=2)

    print()
    print("Success. Saved fresh refresh_token to pointt_credentials.json.")
    print("Update custom_components/bosch_pointt/const.py's REFRESH_TOKEN with the")
    print("same value if you're using the hardcoded-token setup in Home Assistant.")


if __name__ == "__main__":
    main()
