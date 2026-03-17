#!/usr/bin/env python3
"""
Replace all `from pylons import ...` and `from pylons.xxx import ...` with
their r2.lib equivalents across the r2/r2/ source tree.

Run from repo root:
    python3 replace_pylons_imports.py
"""

import re
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), 'r2', 'r2')

# ---------------------------------------------------------------------------
# Mapping: what each pylons name becomes
# ---------------------------------------------------------------------------

# These come from r2.lib.context
CONTEXT_NAMES = {'request', 'response', 'session', 'config', 'url'}
# tmpl_context is aliased as c, but the import is `from pylons import tmpl_context as c`
# We handle it separately via regex

# These come from r2.lib.app_globals
GLOBALS_NAMES = {'app_globals'}  # aliased as g

# These come from r2.lib.i18n
I18N_NAMES = {'_', 'ungettext', 'N_', 'get_lang', 'LanguageError',
              '_get_translator', 'translation', 'NullTranslations'}

# controller utilities
CONTROLLER_UTIL_NAMES = {'abort', 'redirect'}

# WSGIController
WSGI_CONTROLLER_NAMES = {'WSGIController'}


def name_to_source(name):
    """Return the import source module for a given imported name."""
    if name in CONTEXT_NAMES:
        return 'r2.lib.context'
    if name == 'tmpl_context':
        return 'r2.lib.context'
    if name in GLOBALS_NAMES:
        return 'r2.lib.app_globals'
    if name in I18N_NAMES:
        return 'r2.lib.i18n'
    if name in CONTROLLER_UTIL_NAMES:
        return 'r2.lib.base'
    if name in WSGI_CONTROLLER_NAMES:
        return 'r2.lib.base'
    # pylons.util stubs — rarely used, leave as-is comment
    return None


def parse_import_names(names_str):
    """
    Parse a comma-separated list like:
        'app_globals as g, tmpl_context as c, request'
    into a list of (raw_name, alias_or_None) tuples.
    """
    result = []
    for part in names_str.split(','):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'(\w+)\s+as\s+(\w+)', part)
        if m:
            result.append((m.group(1), m.group(2)))
        else:
            result.append((part, None))
    return result


def build_replacement_imports(parsed_names):
    """
    Given a list of (name, alias) tuples from a single `from pylons import ...`
    line, group them by source module and return replacement import lines.
    """
    by_module = {}
    for raw_name, alias in parsed_names:
        src = name_to_source(raw_name)
        if src is None:
            # Unknown — emit a comment so we can find it
            by_module.setdefault('__unknown__', []).append((raw_name, alias))
        else:
            by_module.setdefault(src, []).append((raw_name, alias))

    lines = []
    for src, names in sorted(by_module.items()):
        if src == '__unknown__':
            for raw_name, alias in names:
                al = f' as {alias}' if alias else ''
                lines.append(f'# TODO pylons compat: from pylons import {raw_name}{al}')
            continue

        # Build: `from r2.lib.xxx import foo as bar, baz`
        # Special rename: app_globals -> g is done via `import g` not the class
        parts = []
        for raw_name, alias in names:
            if raw_name == 'tmpl_context' and alias == 'c':
                # Canonical: from r2.lib.context import c
                parts.append('c')
            elif raw_name == 'app_globals' and alias == 'g':
                # Canonical: from r2.lib.app_globals import g
                parts.append('g')
            elif alias and alias != raw_name:
                parts.append(f'{raw_name} as {alias}')
            else:
                parts.append(raw_name)
        lines.append(f'from {src} import {", ".join(parts)}')

    return lines


def replace_pylons_imports_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    lines = original.splitlines(keepends=True)
    new_lines = []
    changed = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # --- `from pylons import ...` (possibly multi-line with backslash or parens)
        m = re.match(r'^(\s*)from pylons\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            indent = m.group(1)
            rest = m.group(2)

            # Collect continuation lines
            while rest.endswith('\\') or (rest.count('(') > rest.count(')')):
                rest = rest.rstrip('\\').rstrip()
                i += 1
                if i >= len(lines):
                    break
                rest += ' ' + lines[i].strip().rstrip('\\').rstrip()

            rest = rest.strip().strip('()')

            parsed = parse_import_names(rest)
            replacement_lines = build_replacement_imports(parsed)
            for rl in replacement_lines:
                new_lines.append(indent + rl + '\n')
            changed = True
            i += 1
            continue

        # --- `from pylons.i18n import ...`
        m = re.match(r'^(\s*)from pylons\.i18n(?:\._translation|\.translation)?\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            indent = m.group(1)
            rest = m.group(2).strip().strip('()')
            parsed = parse_import_names(rest)
            parts = []
            for raw_name, alias in parsed:
                if alias and alias != raw_name:
                    parts.append(f'{raw_name} as {alias}')
                else:
                    parts.append(raw_name)
            new_lines.append(indent + f'from r2.lib.i18n import {", ".join(parts)}\n')
            changed = True
            i += 1
            continue

        # --- `from pylons.controllers.util import abort` / `redirect`
        m = re.match(r'^(\s*)from pylons\.controllers\.util\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            indent = m.group(1)
            rest = m.group(2).strip()
            new_lines.append(indent + f'from r2.lib.base import {rest}\n')
            changed = True
            i += 1
            continue

        # --- `from pylons.controllers import WSGIController`
        m = re.match(r'^(\s*)from pylons\.controllers\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            indent = m.group(1)
            rest = m.group(2).strip()
            new_lines.append(indent + f'from r2.lib.base import {rest}\n')
            changed = True
            i += 1
            continue

        # --- `from pylons.configuration import PylonsConfig`
        m = re.match(r'^(\s*)from pylons\.configuration\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            # PylonsConfig is not needed; emit a no-op stub comment
            new_lines.append(m.group(1) + '# PylonsConfig removed (pylons migration)\n')
            changed = True
            i += 1
            continue

        # --- `from pylons.util import ...`
        m = re.match(r'^(\s*)from pylons\.util\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            new_lines.append(m.group(1) + '# pylons.util stubs removed (pylons migration): ' + m.group(2).strip() + '\n')
            changed = True
            i += 1
            continue

        # --- `from pylons.error import ...`
        m = re.match(r'^(\s*)from pylons\.error\s+import\s+(.*)', line.rstrip('\n\r'))
        if m:
            new_lines.append(m.group(1) + '# pylons.error removed (pylons migration)\n')
            changed = True
            i += 1
            continue

        # --- `import pylons._context as _pylons_ctx`
        m = re.match(r'^(\s*)import pylons\._context\s+as\s+(\w+)', line.rstrip('\n\r'))
        if m:
            indent = m.group(1)
            alias = m.group(2)
            new_lines.append(indent + f'import r2.lib.context as {alias}\n')
            changed = True
            i += 1
            continue

        # --- `import pylons` (bare)
        m = re.match(r'^(\s*)import pylons\s*$', line.rstrip('\n\r'))
        if m:
            new_lines.append(m.group(1) + '# import pylons removed (pylons migration)\n')
            changed = True
            i += 1
            continue

        new_lines.append(line)
        i += 1

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False


def main():
    changed_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Skip __pycache__
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            fp = os.path.join(dirpath, fn)
            if replace_pylons_imports_in_file(fp):
                changed_files.append(fp)

    print(f"Updated {len(changed_files)} files:")
    for f in sorted(changed_files):
        print(f"  {f}")


if __name__ == '__main__':
    main()
