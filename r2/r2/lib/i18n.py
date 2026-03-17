"""
Internationalization helpers for theorangedit.

The active translation object is set per-request via set_lang().
All callsites import from here::

    from r2.lib.i18n import _, ungettext, N_, get_lang
"""

from contextvars import ContextVar

_translation_var: ContextVar = ContextVar('r2.translation', default=None)


def set_lang(translation_obj):
    """Set the active translation for the current request."""
    _translation_var.set(translation_obj)


def _get_translation():
    return _translation_var.get()


def _(s):
    """Translate string s using the active request locale."""
    t = _get_translation()
    if t is None:
        return s
    return t.ugettext(s)


def ungettext(singular, plural, n):
    """Plural-aware translation."""
    t = _get_translation()
    if t is None:
        return singular if n == 1 else plural
    return t.ungettext(singular, plural, n)


def get_lang():
    """Return the active language code list, e.g. ['en']."""
    t = _get_translation()
    if t is None:
        return ['en']
    return getattr(t, 'lang', ['en'])


def N_(s):
    """Mark a string for translation without translating it now."""
    return s


class LanguageError(Exception):
    """Raised when a requested language cannot be activated."""
    pass
