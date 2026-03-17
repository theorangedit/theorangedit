#!/usr/bin/env python3
"""
Python 2 -> 3 migration script for theorangedit.
Handles patterns that 2to3/pyupgrade cover, using text/regex transforms
so the script itself can run on Python 3.13 without needing lib2to3.

Run from repo root:
    python3 migrate_py2to3.py [--dry-run] [path...]
"""

import re
import sys
import os
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Each transform is a (pattern, replacement, description) tuple.
# Applied in order. Use functions where context matters.
# ---------------------------------------------------------------------------

REGEX_TRANSFORMS = [
    # --- imports ---
    (r'\bcPickle\b',                    'pickle',               'cPickle -> pickle'),
    (r'\bcStringIO\b',                  'io',                   'cStringIO -> io'),
    (r'^import ConfigParser\b',         'import configparser',  'ConfigParser -> configparser'),
    (r'\bConfigParser\.ConfigParser\b', 'configparser.ConfigParser', 'ConfigParser.ConfigParser'),
    (r'\bConfigParser\.Error\b',        'configparser.Error',   'ConfigParser.Error'),
    (r'\bConfigParser\.SafeConfigParser\b', 'configparser.SafeConfigParser', 'ConfigParser.SafeConfigParser'),
    (r'\bConfigParser\.NoSectionError\b', 'configparser.NoSectionError', 'ConfigParser.NoSectionError'),
    (r'\bConfigParser\.NoOptionError\b',  'configparser.NoOptionError',  'ConfigParser.NoOptionError'),
    (r'\bfrom StringIO import StringIO\b', 'from io import StringIO', 'StringIO import'),
    (r'\bimport StringIO\b',            'import io',            'import StringIO -> io'),
    (r'\bStringIO\.StringIO\b',         'io.StringIO',          'StringIO.StringIO -> io.StringIO'),

    # urllib reorganization
    (r'\bfrom urllib import quote_plus\b',   'from urllib.parse import quote_plus',   'urllib.quote_plus'),
    (r'\bfrom urllib import quote\b',        'from urllib.parse import quote',         'urllib.quote'),
    (r'\bfrom urllib import unquote_plus\b', 'from urllib.parse import unquote_plus', 'urllib.unquote_plus'),
    (r'\bfrom urllib import unquote\b',      'from urllib.parse import unquote',       'urllib.unquote'),
    (r'\bfrom urllib import urlencode\b',    'from urllib.parse import urlencode',     'urllib.urlencode'),
    (r'\bfrom urllib import urlopen\b',      'from urllib.request import urlopen',     'urllib.urlopen'),
    (r'\bfrom urllib import pathname2url\b', 'from urllib.request import pathname2url','urllib.pathname2url'),
    (r'\bimport urllib2\b',                  'import urllib.request as urllib2',       'import urllib2'),
    (r'\bfrom urllib2 import urlopen\b',     'from urllib.request import urlopen',     'urllib2.urlopen'),
    (r'\bfrom urllib2 import Request\b',     'from urllib.request import Request',     'urllib2.Request'),
    (r'\bfrom urllib2 import HTTPError\b',   'from urllib.request import HTTPError',   'urllib2.HTTPError'),
    (r'\bfrom urllib2 import URLError\b',    'from urllib.error import URLError',      'urllib2.URLError'),
    (r'\bfrom urlparse import urlparse\b',   'from urllib.parse import urlparse',      'urlparse.urlparse'),
    (r'\bfrom urlparse import urlunparse\b', 'from urllib.parse import urlunparse',    'urlparse.urlunparse'),
    (r'\bfrom urlparse import urljoin\b',    'from urllib.parse import urljoin',       'urlparse.urljoin'),
    (r'\bfrom urlparse import urlsplit\b',   'from urllib.parse import urlsplit',      'urlparse.urlsplit'),
    (r'\bfrom urlparse import urlunsplit\b', 'from urllib.parse import urlunsplit',    'urlparse.urlunsplit'),
    (r'\bfrom urlparse import parse_qs\b',   'from urllib.parse import parse_qs',      'urlparse.parse_qs'),
    (r'\bfrom urlparse import parse_qsl\b',  'from urllib.parse import parse_qsl',     'urlparse.parse_qsl'),
    (r'\bimport urlparse\b',                 'import urllib.parse as urlparse',        'import urlparse'),
    (r'\burlparse\.urlparse\b',              'urllib.parse.urlparse',                  'urlparse.urlparse'),
    (r'\burlparse\.urljoin\b',               'urllib.parse.urljoin',                   'urlparse.urljoin'),
    (r'\burlparse\.urlunparse\b',            'urllib.parse.urlunparse',                'urlparse.urlunparse'),
    (r'\burlparse\.urlencode\b',             'urllib.parse.urlencode',                 'urlparse.urlencode'),
    (r'\burlparse\.parse_qs\b',              'urllib.parse.parse_qs',                  'urlparse.parse_qs'),
    (r'\burllib\.quote\b',                   'urllib.parse.quote',                     'urllib.quote'),
    (r'\burllib\.urlencode\b',               'urllib.parse.urlencode',                 'urllib.urlencode'),
    (r'\burllib\.unquote\b',                 'urllib.parse.unquote',                   'urllib.unquote'),

    # --- builtins / types ---
    (r'\bxrange\(',                     'range(',               'xrange -> range'),
    (r'\bbasestring\b',                 'str',                  'basestring -> str'),
    (r'\bunicode\(',                    'str(',                  'unicode() -> str()'),
    # 'unicode' as a type annotation / isinstance check (not function call)
    (r'\bisinstance\(([^,]+),\s*unicode\)', r'isinstance(\1, str)', 'isinstance unicode'),
    (r'\blong\(',                       'int(',                  'long() -> int()'),
    (r'\bhas_key\(([^)]+)\)',           r'(\1 in \0)',           None),  # handled separately below
    (r'\breload\(',                     'importlib.reload(',     'reload -> importlib.reload'),

    # --- itertools Python 2 only ---
    (r'\bfrom itertools import imap\b',    'from builtins import map',    'imap'),
    (r'\bfrom itertools import ifilter\b', 'from builtins import filter', 'ifilter'),
    (r'\bfrom itertools import izip\b',    'from builtins import zip',    'izip'),
    (r'\bitertools\.imap\b',               'map',                         'itertools.imap'),
    (r'\bitertools\.ifilter\b',            'filter',                      'itertools.ifilter'),
    (r'\bitertools\.izip\b',               'zip',                         'itertools.izip'),
    (r'\bimap\(',                          'map(',                        'imap('),
    (r'\bifilter\(',                       'filter(',                     'ifilter('),
    (r'\bizip\(',                          'zip(',                        'izip('),

    # --- dict methods ---
    (r'\.iteritems\(\)',                '.items()',              '.iteritems() -> .items()'),
    (r'\.itervalues\(\)',               '.values()',             '.itervalues() -> .values()'),
    (r'\.iterkeys\(\)',                 '.keys()',               '.iterkeys() -> .keys()'),

    # --- reduce ---
    (r'\breduce\(',                     'functools.reduce(',     'reduce -> functools.reduce'),

    # --- raise syntax: raise Foo, "bar" -> raise Foo("bar") ---
    # handled in the function below (multi-token)

    # --- except syntax: except Foo, e: -> except Foo as e: ---
    # handled in the function below

    # --- print statements: print x -> print(x) ---
    # handled in the function below (complex)

    # --- octal literals: 0777 -> 0o777 ---
    # handled in the function below

    # --- remove __future__ imports that are now default ---
    (r'^from __future__ import print_function\s*\n?', '', '__future__ print_function'),
    (r'^from __future__ import unicode_literals\s*\n?', '', '__future__ unicode_literals'),
    (r'^from __future__ import division\s*\n?', '', '__future__ division'),
    (r'^from __future__ import absolute_import\s*\n?', '', '__future__ absolute_import'),
    (r'^from __future__ import with_statement\s*\n?', '', '__future__ with_statement'),
]


def transform_raise(source):
    """Convert: raise ExcType, "msg"  ->  raise ExcType("msg")"""
    # raise Foo, bar  (where bar can be a string, variable, etc.)
    pattern = re.compile(r'\braise\s+([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*(.*?)(\s*#.*)?$', re.MULTILINE)
    def repl(m):
        comment = m.group(3) or ''
        return f'raise {m.group(1)}({m.group(2)}){comment}'
    return pattern.sub(repl, source)


def transform_except(source):
    """Convert: except Foo, e:  ->  except Foo as e:"""
    pattern = re.compile(r'\bexcept\s+([A-Za-z_][A-Za-z0-9_.,\s]*),\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', re.MULTILINE)
    def repl(m):
        exc_types = m.group(1).strip()
        var = m.group(2)
        return f'except {exc_types} as {var}:'
    return pattern.sub(repl, source)


def transform_has_key(source):
    """Convert: d.has_key(x)  ->  x in d"""
    # Simple single-variable case: obj.has_key(expr)
    pattern = re.compile(r'([A-Za-z_][A-Za-z0-9_\[\]\'\"\.]*)\s*\.\s*has_key\s*\(([^)]+)\)')
    def repl(m):
        return f'({m.group(2)} in {m.group(1)})'
    return pattern.sub(repl, source)


def transform_print_statements(source):
    """
    Convert bare print statements to print() calls.
    Only handles the most common patterns safely — complex cases flagged with TODO.
    """
    lines = source.split('\n')
    result = []
    for line in lines:
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]

        # Skip if already a function call
        if re.match(r'print\s*\(', stripped):
            result.append(line)
            continue

        # print statement (not in a string/comment context — best-effort)
        m = re.match(r'^print\s+(.*?)(\s*#.*)?$', stripped)
        if m and not stripped.startswith('print_') and not stripped.startswith('printer'):
            args = m.group(1).rstrip()
            comment = m.group(2) or ''
            if args.startswith('>>'):
                # print >> sys.stderr, "msg" -> print("msg", file=sys.stderr)
                file_m = re.match(r'>>\s*([^,]+),\s*(.*)', args)
                if file_m:
                    result.append(f'{indent}print({file_m.group(2)}, file={file_m.group(1).strip()}){comment}')
                else:
                    result.append(f'{indent}print({args}){comment}  # TODO: check print conversion')
            elif args == '':
                result.append(f'{indent}print(){comment}')
            else:
                result.append(f'{indent}print({args}){comment}')
        else:
            result.append(line)
    return '\n'.join(result)


def transform_octal_literals(source):
    """Convert 0777 -> 0o777 octal literals."""
    # Match octal literals: 0 followed by digits 0-7 (not 0x, 0b, 0o already)
    pattern = re.compile(r'\b0([0-7]+)\b')
    def repl(m):
        digits = m.group(1)
        # Make sure it's actually meant as octal (has leading 0 + octal digits)
        return f'0o{digits}'
    return pattern.sub(repl, source)


def add_functools_import(source):
    """Add 'import functools' if functools.reduce is used but functools not imported."""
    if 'functools.reduce' in source and 'import functools' not in source:
        # Insert after the last import block
        lines = source.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import = i
        lines.insert(last_import + 1, 'import functools')
        return '\n'.join(lines)
    return source


def add_importlib_import(source):
    """Add 'import importlib' if importlib.reload is used but importlib not imported."""
    if 'importlib.reload' in source and 'import importlib' not in source:
        lines = source.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import = i
        lines.insert(last_import + 1, 'import importlib')
        return '\n'.join(lines)
    return source


def apply_transforms(source, filepath):
    changes = []

    # Apply regex transforms
    for item in REGEX_TRANSFORMS:
        if item[2] is None:
            continue  # skip placeholder entries
        pattern, replacement, desc = item
        new_source, count = re.subn(pattern, replacement, source, flags=re.MULTILINE)
        if count:
            changes.append(f'  {count}x {desc}')
            source = new_source

    # Apply function-based transforms
    for fn, desc in [
        (transform_raise,            'raise Foo, msg -> raise Foo(msg)'),
        (transform_except,           'except Foo, e -> except Foo as e'),
        (transform_has_key,          '.has_key() -> in'),
        (transform_print_statements, 'print stmt -> print()'),
        (add_functools_import,       'add functools import'),
        (add_importlib_import,       'add importlib import'),
    ]:
        new_source = fn(source)
        if new_source != source:
            changes.append(f'  {desc}')
            source = new_source

    return source, changes


def process_file(path, dry_run=False):
    try:
        original = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f'ERROR reading {path}: {e}')
        return False

    new_source, changes = apply_transforms(original, path)

    if new_source == original:
        return False

    print(f'\n{path}')
    for c in changes:
        print(c)

    if not dry_run:
        path.write_text(new_source, encoding='utf-8')

    return True


def main():
    parser = argparse.ArgumentParser(description='Python 2->3 migration for theorangedit')
    parser.add_argument('paths', nargs='*', default=['r2'], help='Paths to process (default: r2/)')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    args = parser.parse_args()

    changed = 0
    skipped = 0

    for root_path in args.paths:
        root = Path(root_path)
        if root.is_file():
            files = [root]
        else:
            files = list(root.rglob('*.py')) + list(root.rglob('*.pyx'))

        for f in sorted(files):
            # Skip venv, build artifacts, .git
            parts = f.parts
            if any(p in parts for p in ['.venv', 'venv', '__pycache__', '.git', 'build', 'dist']):
                continue
            if process_file(f, dry_run=args.dry_run):
                changed += 1
            else:
                skipped += 1

    print(f'\n{"DRY RUN: " if args.dry_run else ""}Done. {changed} files changed, {skipped} files unchanged.')


if __name__ == '__main__':
    main()
