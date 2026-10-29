"""Build an installable archive without bytecode or credentials."""
from pathlib import Path
import json
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
version = json.loads((root / "custom_components/mgroup_light/manifest.json").read_text())["version"]
output = root / f"dist/mgroup_light-{version}.zip"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for source in sorted((root / "custom_components/mgroup_light").rglob("*")):
        if source.is_file() and source.suffix in {".py", ".json"}:
            archive.write(source, source.relative_to(root))
print(output)
