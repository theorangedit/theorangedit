# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################

import inspect

from r2.lib.app_globals import g


class _NullTemplate:
    """Stub returned when no template is found; renders empty string."""
    is_null = True

    def render(self, **kw):
        return ''


NULL_TEMPLATE = _NullTemplate()


class _Jinja2TemplateWrapper:
    """
    Thin wrapper around a Jinja2 Template that exposes the same
    ``template.render(thing=obj, **kw)`` interface the rest of the
    codebase expects.

    The Jinja2 template is rendered with the request context variables
    (g, c, request) injected automatically so templates can reference
    them without explicit imports.
    """
    is_null = False

    def __init__(self, jinja_template, filename=None):
        self._tmpl = jinja_template
        self.filename = filename

    def render(self, thing=None, **kw):
        from r2.lib.context import c, request
        from r2.lib.i18n import _, ungettext, N_, get_lang
        from r2.lib.template_helpers import (
            static, add_sr, get_domain,
        )
        from r2.lib.filters import unsafe, safemarkdown, websafe

        ctx = dict(
            thing=thing,
            g=g,
            c=c,
            request=request,
            # i18n
            _=_,
            ungettext=ungettext,
            N_=N_,
            get_lang=get_lang,
            # common helpers
            static=static,
            add_sr=add_sr,
            get_domain=get_domain,
            unsafe=unsafe,
            safemarkdown=safemarkdown,
            websafe=websafe,
            # builtins
            getattr=getattr,
            hasattr=hasattr,
            isinstance=isinstance,
            len=len,
            str=str,
            int=int,
            list=list,
            dict=dict,
            enumerate=enumerate,
            sorted=sorted,
            zip=zip,
            range=range,
        )
        ctx.update(kw)
        return self._tmpl.render(**ctx)


class tp_manager:
    def __init__(self):
        self.templates = {}
        self.cache_override_styles = set()

    def add_handler(self, name, style, handler):
        """Register a JSON template handler for a given class name + style."""
        key = (name.lower(), style.lower())
        self.templates[key] = handler
        self.cache_override_styles.add(style.lower())

    def _get_jinja_template(self, cls, style):
        """
        Look up a Jinja2 template file for ``cls`` at style ``style``.

        Template files are named ``<classname>.<style>`` (e.g. ``link.html``).
        Walks the MRO to find the closest match.
        """
        jinja_env = getattr(g, 'jinja_env', None)
        if jinja_env is None:
            return None

        classes = [cls] + list(inspect.getmro(cls)[1:])
        for klass in classes:
            filename = '/%s.%s' % (klass.__name__.lower(), style)
            try:
                tmpl = jinja_env.get_template(filename)
                return _Jinja2TemplateWrapper(tmpl, filename=filename)
            except Exception:
                continue
        return None

    def get_template(self, cls, style):
        name = cls.__name__.lower()
        use_cache = not getattr(g, 'reload_templates', False)

        if use_cache or style.lower() in self.cache_override_styles:
            key = (name, style)
            tmpl = self.templates.get(key)
            if tmpl:
                return tmpl

        tmpl = self._get_jinja_template(cls, style)
        if tmpl and use_cache:
            self.templates[(name, style)] = tmpl
        return tmpl

    def get(self, thing, style):
        if not isinstance(thing, type(object)):
            thing = thing.__class__

        style = style.lower()
        template = self.get_template(thing, style)
        if template:
            return template

        # Walk MRO for a matching template
        for cls in inspect.getmro(thing)[1:]:
            template = self.get_template(cls, style)
            if template:
                break
        else:
            template = NULL_TEMPLATE

        # Cache so we skip the MRO walk next time
        if not getattr(g, 'reload_templates', False):
            self.templates[(thing.__name__.lower(), style)] = template

        return template
