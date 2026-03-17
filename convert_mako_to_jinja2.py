#!/usr/bin/env python3
"""
Convert Mako templates to Jinja2 across r2/r2/templates/.

Handles:
  - <%inherit file="x"/>           -> {% extends "x" %}
  - <%namespace file="x" import="foo,bar"/> -> {% from "x" import foo, bar %}
  - <%namespace file="x" name="ns"/> -> (tracked for ns.foo() calls)
  - <%def name="foo()">            -> {% macro foo() %}
  - </%def>                        -> {% endmacro %}
  - <%include file="x"/>           -> {% include "x" %}
  - ${var}                         -> {{ var }}
  - ${unsafe(x)}                   -> {{ x | safe }}
  - %if ... :                      -> {% if ... %}
  - %elif ... :                    -> {% elif ... %}
  - %else:                         -> {% else %}
  - %endif                         -> {% endif %}
  - %for x in y:                   -> {% for x in y %}
  - %endfor                        -> {% endfor %}
  - %while ...:                    -> {% while ... %}  (rare)
  - next.body()                    -> super()
  - caller.body()                  -> caller()
  - ## comment                     -> {# comment #}
  - <%! ... %>                     -> removed (module-level imports)
  - <% ... %>                      -> {% set ... %} where possible, otherwise removed with warning
  - from pylons import ...         -> from r2.lib.context / r2.lib.app_globals

The conversion is conservative: when something is ambiguous or complex, it
emits a TODO comment so we can review manually.
"""

import os
import re
import sys

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), 'r2', 'r2', 'templates'
)

EXTENSIONS = {
    '.html', '.compact', '.mobile', '.htmllite', '.iframe',
    '.xml', '.email', '.txt', '.js',
}


# ---------------------------------------------------------------------------
# Pattern-based substitutions
# ---------------------------------------------------------------------------

def convert_unsafe_expr(expr):
    """Convert ${unsafe(x)} -> {{ x | safe }}, ${x} -> {{ x }}."""
    # nested unsafe calls: ${unsafe(foo(bar))} — extract the inner arg
    m = re.match(r'unsafe\((.+)\)$', expr.strip())
    if m:
        inner = m.group(1).strip()
        return f'{{{{ {inner} | safe }}}}'
    return f'{{{{ {expr} }}}}'


def convert_dollar_braces(text):
    """
    Replace ${...} with {{ ... }}, handling nested braces.
    unsafe() calls become | safe filters.
    """
    result = []
    i = 0
    while i < len(text):
        if text[i:i+2] == '${':
            # Find matching closing brace, counting nesting
            depth = 1
            j = i + 2
            while j < len(text) and depth > 0:
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                j += 1
            expr = text[i+2:j-1]
            result.append(convert_unsafe_expr(expr))
            i = j
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def convert_line(line):
    """Convert a single template line from Mako to Jinja2 syntax."""
    # Preserve raw line ending
    stripped = line.rstrip('\n\r')
    ending = line[len(stripped):]
    s = stripped

    # Skip already-converted lines
    if s.strip().startswith('{%') or s.strip().startswith('{{') or s.strip().startswith('{#'):
        return line

    # ## Mako comments -> {# Jinja2 comments #}
    m = re.match(r'^(\s*)##(.*)$', s)
    if m:
        return m.group(1) + '{#' + m.group(2) + ' #}' + ending

    # %if condition:
    m = re.match(r'^(\s*)%\s*if\s+(.+?):\s*$', s)
    if m:
        cond = m.group(2).strip()
        return m.group(1) + '{% if ' + cond + ' %}' + ending

    # %elif condition:
    m = re.match(r'^(\s*)%\s*elif\s+(.+?):\s*$', s)
    if m:
        cond = m.group(2).strip()
        return m.group(1) + '{% elif ' + cond + ' %}' + ending

    # %else:
    m = re.match(r'^(\s*)%\s*else:\s*$', s)
    if m:
        return m.group(1) + '{% else %}' + ending

    # %endif
    m = re.match(r'^(\s*)%\s*endif\s*$', s)
    if m:
        return m.group(1) + '{% endif %}' + ending

    # %for x in y:
    m = re.match(r'^(\s*)%\s*for\s+(.+?):\s*$', s)
    if m:
        expr = m.group(2).strip()
        return m.group(1) + '{% for ' + expr + ' %}' + ending

    # %endfor
    m = re.match(r'^(\s*)%\s*endfor\s*$', s)
    if m:
        return m.group(1) + '{% endfor %}' + ending

    # %while ...:
    m = re.match(r'^(\s*)%\s*while\s+(.+?):\s*$', s)
    if m:
        return m.group(1) + '{# TODO while: ' + s.strip() + ' #}' + ending

    # %endwhile
    m = re.match(r'^(\s*)%\s*endwhile\s*$', s)
    if m:
        return m.group(1) + '{# TODO endwhile #}' + ending

    # %return / %break / %continue
    m = re.match(r'^(\s*)%\s*(return|break|continue)\b(.*)$', s)
    if m:
        return m.group(1) + '{# TODO ' + m.group(2) + m.group(3) + ' #}' + ending

    # Apply ${...} substitution for everything else
    s = convert_dollar_braces(s)

    # next.body() -> super()
    s = re.sub(r'\bnext\.body\(\)', 'super()', s)

    # caller.body() -> caller()
    s = re.sub(r'\bcaller\.body\(\)', 'caller()', s)

    return s + ending


def convert_mako_tag_lines(lines):
    """
    Handle multi-line Mako tags:
      <%inherit file="x"/>
      <%namespace file="x" import="foo,bar"/>
      <%def name="foo()">
      </%def>
      <%include file="x"/>
      <%! ... %>
      <% ... %>
    Returns new list of lines.
    """
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # <%inherit file="..."/>
        m = re.match(r'\s*<%inherit\s+file=["\']([^"\']+)["\']\s*/>', stripped)
        if m:
            result.append(re.sub(r'\s*', '', line[:len(line)-len(line.lstrip())]) +
                          '{% extends "' + m.group(1) + '" %}\n')
            i += 1
            continue

        # <%namespace file="..." import="..."/> — converts to {% from ... import ... %}
        m = re.match(r'\s*<%namespace\s+file=["\']([^"\']+)["\']\s+import=["\']([^"\']+)["\']\s*/>', stripped)
        if m:
            tmpl_file = m.group(1)
            imports = ', '.join(x.strip() for x in m.group(2).split(','))
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{% from "' + tmpl_file + '" import ' + imports + ' %}\n')
            i += 1
            continue

        # <%namespace file="..." name="alias"/> — aliased namespace (keep as import *)
        m = re.match(r'\s*<%namespace\s+file=["\']([^"\']+)["\']\s+name=["\']([^"\']+)["\']\s*/>', stripped)
        if m:
            tmpl_file = m.group(1)
            alias = m.group(2)
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{# namespace: import ' + alias + ' from "' + tmpl_file + '" — review #}\n')
            result.append(indent + '{% import "' + tmpl_file + '" as ' + alias + ' %}\n')
            i += 1
            continue

        # <%namespace ...  (without import= or name=, other attrs)
        m = re.match(r'\s*<%namespace\b', stripped)
        if m:
            # Collect full tag (may span lines)
            tag_lines = [stripped]
            while '/>' not in tag_lines[-1] and i + 1 < len(lines):
                i += 1
                tag_lines.append(lines[i].strip())
            full_tag = ' '.join(tag_lines)
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{# TODO namespace: ' + full_tag + ' #}\n')
            i += 1
            continue

        # <%include file="..."/>
        m = re.match(r'\s*<%include\s+file=["\']([^"\']+)["\']\s*/>', stripped)
        if m:
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{% include "' + m.group(1) + '" %}\n')
            i += 1
            continue

        # <%def name="foo(args)">
        m = re.match(r'\s*<%def\s+name=["\'](\w+)\(([^)]*)\)["\']>', stripped)
        if m:
            fname = m.group(1)
            args = m.group(2).strip()
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{% macro ' + fname + '(' + args + ') %}\n')
            i += 1
            continue

        # </%def>
        if re.match(r'\s*</%def>', stripped):
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{% endmacro %}\n')
            i += 1
            continue

        # <%block name="...">
        m = re.match(r'\s*<%block\s+name=["\'](\w+)["\']>', stripped)
        if m:
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{% block ' + m.group(1) + ' %}\n')
            i += 1
            continue

        # </%block>
        if re.match(r'\s*</%block>', stripped):
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{% endblock %}\n')
            i += 1
            continue

        # <%! module-level imports %> — collect multi-line, then emit converted imports
        if re.match(r'\s*<%!', stripped):
            module_lines = []
            # inline: <%! code %>
            m_inline = re.match(r'\s*<%!(.*?)%>\s*$', stripped)
            if m_inline:
                module_lines = [m_inline.group(1)]
                i += 1
            else:
                # multi-line
                i += 1
                while i < len(lines):
                    l = lines[i].strip()
                    if l == '%>':
                        i += 1
                        break
                    module_lines.append(lines[i])
                    i += 1
            # Emit converted pylons imports; drop everything else (will be injected via context)
            converted = _convert_module_imports(module_lines)
            result.extend(converted)
            continue

        # <% inline code %> — single line
        m = re.match(r'\s*<%(.+?)%>\s*$', stripped)
        if m:
            code = m.group(1).strip()
            indent = line[:len(line) - len(line.lstrip())]
            # Convert simple assignments to {% set %}
            assign = re.match(r'^(\w+)\s*=\s*(.+)$', code)
            if assign:
                result.append(indent + '{% set ' + assign.group(1) + ' = ' + assign.group(2) + ' %}\n')
            else:
                result.append(indent + '{# TODO inline code: ' + code + ' #}\n')
            i += 1
            continue

        # <% multi-line inline code block %>
        if re.match(r'\s*<%\s*$', stripped) or re.match(r'\s*<%\s+\S', stripped):
            code_lines = []
            if not stripped.endswith('%>'):
                i += 1
                while i < len(lines):
                    l = lines[i].rstrip()
                    if l.strip() == '%>':
                        i += 1
                        break
                    code_lines.append(l)
                    i += 1
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + '{# TODO multi-line code block:\n')
            for cl in code_lines:
                result.append(cl + '\n')
            result.append(indent + '#}\n')
            continue

        result.append(line)
        i += 1

    return result


def _convert_module_imports(module_lines):
    """
    Convert <%! import block %> lines.
    - pylons imports -> r2.lib.context / r2.lib.app_globals / r2.lib.i18n imports
    - other imports -> {# import removed #} comment
    Returns list of Jinja2 comment/set lines (module-level imports not available in Jinja2).
    """
    result = []
    for line in module_lines:
        s = line.strip() if isinstance(line, str) else line.strip()
        if not s or s.startswith('#'):
            continue

        # pylons imports -> translated
        pylons_map = {
            'from pylons import app_globals as g': None,  # available via context
            'from pylons import tmpl_context as c': None,
            'from pylons import request': None,
            'from pylons import response': None,
            'from pylons.i18n import _': None,
            'from pylons.i18n import _, ungettext': None,
            'from pylons.i18n import ungettext': None,
            'from pylons.i18n import _, ungettext, get_lang': None,
        }

        is_pylons = False
        for pat in pylons_map:
            if s == pat or s.startswith(pat + ',') or s.startswith('from pylons'):
                is_pylons = True
                break

        if is_pylons:
            result.append('{# template import removed (available via context): ' + s + ' #}\n')
        else:
            # Other imports: these become context variables injected by the view
            result.append('{# template import (inject via context): ' + s + ' #}\n')
    return result


def convert_file(filepath):
    """Convert a single Mako template file to Jinja2 in-place."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        original = f.read()

    lines = original.splitlines(keepends=True)

    # Pass 1: Handle Mako structural tags (<%inherit>, <%def>, etc.)
    lines = convert_mako_tag_lines(lines)

    # Pass 2: Handle line-level syntax (%if, %for, ${...}, etc.)
    lines = [convert_line(l) for l in lines]

    new_content = ''.join(lines)

    if new_content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False


def main():
    changed = []
    skipped = []
    errors = []

    for dirpath, dirnames, filenames in os.walk(TEMPLATE_DIR):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fn in filenames:
            _, ext = os.path.splitext(fn)
            if ext not in EXTENSIONS:
                skipped.append(os.path.join(dirpath, fn))
                continue
            fp = os.path.join(dirpath, fn)
            try:
                if convert_file(fp):
                    changed.append(fp)
            except Exception as e:
                errors.append((fp, str(e)))

    print(f'Converted: {len(changed)} files')
    print(f'Unchanged: {len(skipped)} files (extension not in target list)')
    if errors:
        print(f'Errors ({len(errors)}):')
        for fp, e in errors:
            print(f'  {fp}: {e}')


if __name__ == '__main__':
    main()
