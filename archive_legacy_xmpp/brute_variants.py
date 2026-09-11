"""Try known-variant key derivations against a captured real ciphertext."""
import base64
import hashlib
import binascii
from pyaes import PADDING_NONE, AESModeOfOperationECB, Decrypter

# real values in keys.txt (gitignored)
ACCESS_KEY = "PASTE_FROM_KEYS_TXT"
PASSWORD_CANDIDATES = ["PASTE_FROM_KEYS_TXT"]
MAGIC = bytearray.fromhex(
    "1d86b2631b02f2c7978b41e8a3ae609b0b2afbfd30ff386da60c586a827408e4"
)
CIPHERTEXT_B64 = (
    "O/hdNPWCdLZr1pKlEFqwsijmk97ELHP6xMlvZu/c1Iru9Ve5aB7lhib3zgEkMWanjVuae7"
    "KO67wlyScV1vb8Aqxu5+K+Dxyh3sPIFsfiFU6emnkO59tZ2Lz+5dG9NEN4"
)


def try_decrypt(key_bytes, label):
    try:
        enc = base64.b64decode(CIPHERTEXT_B64)
        if len(enc) % 16 != 0:
            return
        cipher = Decrypter(AESModeOfOperationECB(key_bytes), padding=PADDING_NONE)
        decrypted = cipher.feed(enc) + cipher.feed()
        text = decrypted.decode("utf-8").rstrip("\x00")
        print(f"[OK ] {label}: {text[:200]!r}")
        if "gateway" in text or "id" in text:
            print(f"  ^^^ LOOKS VALID (key len {len(key_bytes)} bytes) key_hex={key_bytes.hex()}")
    except Exception as e:
        pass  # noqa


def md5_variant(a, b):
    return hashlib.md5(a).hexdigest()


for password in PASSWORD_CANDIDATES:
    ak = bytearray(ACCESS_KEY, "utf8")
    pw = bytearray(password, "utf8")

    # 1. Baseline (already known to fail, sanity check)
    key_hash = hashlib.md5(ak + MAGIC).hexdigest()
    pass_hash = hashlib.md5(MAGIC + pw).hexdigest()
    try_decrypt(binascii.unhexlify(key_hash + pass_hash), f"baseline pw={password}")

    # 2. Swapped order: password_hash + key_hash
    try_decrypt(binascii.unhexlify(pass_hash + key_hash), f"swapped pw={password}")

    # 3. Magic on both sides swapped (access_key after magic, password before magic)
    key_hash2 = hashlib.md5(MAGIC + ak).hexdigest()
    pass_hash2 = hashlib.md5(pw + MAGIC).hexdigest()
    try_decrypt(binascii.unhexlify(key_hash2 + pass_hash2), f"magic-swapped pw={password}")

    # 4. SHA256 instead of MD5, truncate each to 16 hex chars -> 32 bytes total
    key_hash3 = hashlib.sha256(ak + MAGIC).hexdigest()[:32]
    pass_hash3 = hashlib.sha256(MAGIC + pw).hexdigest()[:32]
    try_decrypt(binascii.unhexlify(key_hash3 + pass_hash3), f"sha256-trunc pw={password}")

    # 5. access_key uppercased / lowercased
    for variant_key in (ACCESS_KEY.upper(), ACCESS_KEY.lower()):
        ak2 = bytearray(variant_key, "utf8")
        kh = hashlib.md5(ak2 + MAGIC).hexdigest()
        ph = hashlib.md5(MAGIC + pw).hexdigest()
        try_decrypt(binascii.unhexlify(kh + ph), f"case-variant key={variant_key} pw={password}")

    # 6. Only access_key as raw material (password ignored), md5 doubled
    kh_only = hashlib.md5(ak + MAGIC).hexdigest()
    try_decrypt(binascii.unhexlify(kh_only + kh_only), f"key-only-doubled pw_ignored")

    # 7. access_key alone, unhex-padded/truncated as if raw hex (will mostly fail length)
    # (skipped: ACCESS_KEY isn't valid hex)

print("Done. If nothing printed [OK] with a valid-looking id/gateway string, all variants failed.")
