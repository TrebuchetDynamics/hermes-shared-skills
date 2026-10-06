#!/usr/bin/env python3
"""Validate first-party root-level skills, not ignored upstream vendor copies.

Requires ruamel.yaml (also shipped in Hermes' runtime). This checks loader
contracts, not prose quality, shell examples, or arbitrary path-like tokens.
"""
import argparse
import re
from pathlib import Path

from ruamel.yaml import YAML


def discover_skills(root):
    root = Path(root).resolve()
    return sorted(path for path in root.glob('*/SKILL.md')
                  if not path.parent.name.startswith('.') and path.parent.name != 'vendor'
                  and not path.parent.is_symlink() and not path.is_symlink()
                  and path.is_file() and root in path.resolve().parents)


def validate_catalog(root):
    root = Path(root).resolve()
    paths = discover_skills(root)
    if not paths:
        return ['No first-party skills found; refusing a vacuous pass.']
    errors = []
    yaml = YAML(typ='safe')
    for path in paths:
        label = str(path.relative_to(root))
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            errors.append(f'{label}: unreadable: {exc}')
            continue
        if len(text) > 100_000:
            errors.append(f'{label}: exceeds 100000 character loader limit')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z', text, re.S)
        if not match:
            errors.append(f'{label}: missing opening/closing frontmatter delimiters')
            continue
        try:
            metadata = yaml.load(match.group(1))
        except Exception as exc:
            errors.append(f'{label}: invalid YAML: {exc}')
            continue
        if not isinstance(metadata, dict):
            errors.append(f'{label}: frontmatter must be a YAML mapping')
            continue
        name = metadata.get('name')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name):
            errors.append(f'{label}: invalid name (lowercase slug, max 64 characters)')
        elif name != path.parent.name:
            errors.append(f'{label}: name {name!r} does not match directory {path.parent.name!r}')
        description = metadata.get('description')
        if not isinstance(description, str) or not description.strip() or len(description) > 60:
            errors.append(f'{label}: description must be a nonempty string, max 60 characters')
        platforms = metadata.get('platforms')
        if platforms is not None and (
            not isinstance(platforms, list) or not platforms or
            any(p not in ('linux', 'macos', 'windows') for p in platforms)
        ):
            errors.append(f'{label}: platforms must be a nonempty list of linux/macos/windows')
        if not match.group(2).strip():
            errors.append(f'{label}: missing skill body')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_catalog(args.root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f'Validated {len(discover_skills(args.root))} first-party skills (vendor excluded).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
