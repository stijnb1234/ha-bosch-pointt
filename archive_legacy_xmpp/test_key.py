import hashlib
import binascii

access_key = input("Access key/token: ")
password = input("EasyControl password: ")

magic = bytearray.fromhex(
    "1d86b2631b02f2c7978b41e8a3ae609b0b2afbfd30ff386da60c586a827408e4"
)

key_hash = hashlib.md5(
    bytearray(access_key, "utf8") + magic
).hexdigest()

password_hash = hashlib.md5(
    magic + bytearray(password, "utf8")
).hexdigest()

saved_key = key_hash + password_hash
aes_key = binascii.unhexlify(saved_key)

print()
print("Key length:", len(aes_key), "bytes")
print("Key:", saved_key)