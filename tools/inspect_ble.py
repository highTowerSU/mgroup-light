"""List one panel's GATT profile without writing commands or pairing.

Requires bleak. Example:
  python tools/inspect_ble.py D4:10:F2:1C:F0:8E
"""
import argparse
import asyncio
import json

from bleak import BleakClient, BleakScanner


async def inspect(address: str) -> dict:
    device = await BleakScanner.find_device_by_address(address, timeout=20)
    if device is None:
        raise RuntimeError(f"Device {address} was not found")
    result = {"address": device.address, "name": device.name, "services": []}
    # On this panel the first BlueZ discovery returned only the first service;
    # the remaining interfaces appeared afterwards. Reconnect once if the
    # expected control characteristic is missing, without clearing pairings.
    control_uuid = "0003cbbb-0000-1000-8000-00805f9beffa"
    for attempt in range(2):
        result["services"] = []
        async with BleakClient(device, timeout=30, pair=False) as client:
            for service in client.services:
                result["services"].append({
                    "uuid": service.uuid,
                    "handle": service.handle,
                    "characteristics": [
                        {
                            "uuid": char.uuid,
                            "handle": char.handle,
                            "properties": char.properties,
                            "descriptors": [
                                {"uuid": desc.uuid, "handle": desc.handle}
                                for desc in char.descriptors
                            ],
                        }
                        for char in service.characteristics
                    ],
                })
            result["control_characteristic_found"] = (
                client.services.get_characteristic(control_uuid) is not None
            )
        if result["control_characteristic_found"]:
            break
        if attempt == 0:
            await asyncio.sleep(1)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(inspect(args.address)), indent=2))
