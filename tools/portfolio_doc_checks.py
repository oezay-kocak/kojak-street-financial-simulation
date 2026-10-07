"""Check publishable Markdown targets, assets and repository hygiene.

This lightweight documentation check does not replace the product test suite.
It checks local links without making network requests or printing secret values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


def heading_ids(text: str) -> set[str]:
    ids: set[str] = set()
    counts: dict[str, int] = {}
    in_code = False
    for line in text.splitlines():
        if line.startswith('```'):
            in_code = not in_code
        if in_code or not re.match(r'^#{1,6} ', line):
            continue
        title = re.sub(r'^#+\s+', '', line).strip().lower()
        title = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        number = counts.get(title, 0)
        counts[title] = number + 1
        ids.add(title if number == 0 else f'{title}-{number}')
    return ids


def check(root: Path) -> dict:
    candidates = subprocess.check_output(
        ['git', 'ls-files', '-c', '-o', '--exclude-standard'], cwd=root, text=True
    ).splitlines()
    files = {p for p in candidates if (root / p).is_file()}
    errors: list[str] = []
    links = 0
    docs = sorted(p for p in files if p.endswith('.md'))
    secret = re.compile(r'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|'
                        r'AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')
    private_path = re.compile(r'[A-Za-z]:[/\\]Users[/\\]', re.IGNORECASE)
    for filename in sorted(files):
        path = root / filename
        if path.stat().st_size > 3_000_000:
            errors.append(f'{filename}: exceeds selected publication size budget')
        if set(path.relative_to(root).parts) & {'.cache', '.venv', '__pycache__', 'artifacts'}:
            errors.append(f'{filename}: private/cache artifact')
        if filename.endswith(('.duckdb', '.duckdb.wal', '.log', '.dat')):
            errors.append(f'{filename}: runtime data artifact')
        if path.suffix not in {'.py', '.md', '.toml', '.yml', '.txt', '.json'}:
            continue
        content = path.read_text(encoding='utf-8')
        if private_path.search(content):
            errors.append(f'{filename}: personal absolute path')
        if secret.search(content):
            errors.append(f'{filename}: potential credential pattern (value withheld)')
        if filename not in docs:
            continue
        targets = re.findall(r'!?\[[^\]\n]*\]\((<[^>]+>|[^)\n]+)\)', content)
        targets += re.findall(r'^\[[^\]\n]+\]:\s*(<[^>]+>|\S+)', content, re.MULTILINE)
        for target in targets:
            target = target.strip().strip('<>')
            parts = urlsplit(target)
            if parts.scheme or parts.netloc:
                if parts.scheme in {'file', 'C', 'c'}:
                    errors.append(f'{filename}: local absolute link')
                continue
            links += 1
            destination = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            try:
                relative = destination.relative_to(root).as_posix()
            except ValueError:
                errors.append(f'{filename}: link outside repository: {target}')
                continue
            if relative not in files:
                errors.append(f'{filename}: non-publishable link: {target}')
            elif (parts.fragment and destination.suffix == '.md'
                  and unquote(parts.fragment) not in heading_ids(destination.read_text(encoding='utf-8'))):
                errors.append(f'{filename}: unknown heading: {target}')
    assets = sorted(p for p in files if p.startswith('docs/assets/'))
    return {'passed': not errors, 'documents': len(docs), 'local_links': links,
            'assets': [{'path': p, 'bytes': (root/p).stat().st_size,
                        'sha256': hashlib.sha256((root/p).read_bytes()).hexdigest()} for p in assets],
            'publication_candidates': len(files), 'errors': errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(Path(__file__).resolve().parents[1])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
