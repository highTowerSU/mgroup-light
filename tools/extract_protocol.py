"""Disassemble relevant app classes without running the supplied Android app.

Requires androguard. Run from the repository root:
  python tools/extract_protocol.py
Generated third-party code stays in ignored analysis/disassembly/.
"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from androguard.core.apk import APK
from androguard.core.dex import DEX
from loguru import logger


def main():
    logger.remove()
    with ZipFile("com.jance.magical.xapk") as archive:
        apk_bytes = archive.read("com.jance.magical.apk")
    apk = APK(apk_bytes, raw=True)
    print(apk.get_app_name(), apk.get_androidversion_name(), apk.get_androidversion_code())
    output = Path("analysis/disassembly")
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    with ZipFile(BytesIO(apk_bytes)) as archive:
        for entry in archive.namelist():
            if not (entry.startswith("classes") and entry.endswith(".dex")):
                continue
            dex = DEX(archive.read(entry))
            for cls in dex.get_classes():
                name = cls.get_name()
                if not name.startswith("Lcom/qunchen/magical/"):
                    continue
                if not any(part in name for part in (
                    "/ble/", "/road/", "/xxutils/", "/bean/RoadLightBean;",
                )):
                    continue
                lines = []
                for method in cls.get_methods():
                    lines.append(f"\nMETHOD {method.get_name()} {method.get_descriptor()}")
                    if method.get_code():
                        for instruction in method.get_instructions():
                            lines.append(f"{instruction.get_name()} {instruction.get_output()}")
                (output / (name[1:-1].replace("/", ".") + ".txt")).write_text(
                    "\n".join(lines), encoding="utf-8"
                )
                count += 1
    print(f"Extracted {count} classes into {output}")


if __name__ == "__main__":
    main()
