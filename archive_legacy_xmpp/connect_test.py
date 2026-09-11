"""Test connection to Bosch EasyControl thermostat via XMPP."""
import asyncio
import logging

from bosch_thermostat_client.gateway import gateway_chooser
from bosch_thermostat_client.const.easycontrol import EASYCONTROL

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("slixmpp").setLevel(logging.INFO)

# real values in keys.txt (gitignored)
SERIAL = "PASTE_FROM_KEYS_TXT"
ACCESS_KEY = "PASTE_FROM_KEYS_TXT"
PASSWORD = "PASTE_FROM_KEYS_TXT"


async def main():
    Gateway = gateway_chooser(EASYCONTROL)
    gateway = Gateway(
        host=SERIAL,
        access_token=ACCESS_KEY,
        password=PASSWORD,
    )
    try:
        uuid = await gateway.check_connection()
        print("UUID:", uuid)
        print("Firmware:", gateway.firmware)
    finally:
        await gateway.close(force=True)


if __name__ == "__main__":
    asyncio.run(main())
