"""Build a clean publishable repository, excluding device captures and app files."""
import argparse
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile


def build(repository: str, output: Path | None = None) -> Path:
    match = re.fullmatch(r'https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?', repository)
    if not match:
        raise ValueError('Use a GitHub URL: https://github.com/OWNER/REPOSITORY')
    owner, name = match.groups()
    url = f'https://github.com/{owner}/{name}'
    root = Path(__file__).resolve().parents[1]
    output = output or root / 'dist/mgroup_light-repository.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'custom_components/mgroup_light/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.update(documentation=url+'#readme', issue_tracker=url+'/issues', codeowners=['@'+owner])
    sources = [root/'README.md', root/'hacs.json', root/'requirements-test.txt', root/'STROMPI2.md', root/'ESP32_PLAN.md']
    for directory in ('custom_components/mgroup_light', 'tests', 'tools', 'blueprints'):
        sources.extend(p for p in (root/directory).rglob('*') if p.is_file() and p.suffix in {'.py', '.json', '.yaml'})
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for source in sorted(sources):
            name = source.relative_to(root).as_posix()
            if source == manifest_path:
                archive.writestr(name, json.dumps(manifest, indent=2)+'\n')
            else:
                archive.write(source, name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    print(build(args.repository))
