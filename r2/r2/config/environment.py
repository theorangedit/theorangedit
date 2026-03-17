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

import os
import mimetypes

from jinja2 import Environment, FileSystemLoader, select_autoescape

import r2.lib.helpers
from r2.config.paths import (
    get_r2_path,
    get_built_statics_path,
    get_raw_statics_path,
)
from r2.lib.app_globals import Globals
from r2.lib.configparse import ConfigValue

import r2.lib.context as _r2_ctx


mimetypes.init()


def load_environment(global_conf={}, app_conf={}, setup_globals=True):
    r2_path = get_r2_path()
    root_path = os.path.join(r2_path, 'r2')

    paths = {
        'root': root_path,
        'controllers': os.path.join(root_path, 'controllers'),
        'templates': [os.path.join(root_path, 'templates')],
    }

    if ConfigValue.bool(global_conf.get('uncompressedJS')):
        paths['static_files'] = get_raw_statics_path()
    else:
        paths['static_files'] = get_built_statics_path()

    config = {}
    config.update(global_conf)
    config.update(app_conf)
    config['r2.paths'] = paths

    # Initialise the application globals singleton.
    g = Globals(config, global_conf, app_conf, paths)

    # Publish g into r2.lib.app_globals so all imports resolve correctly.
    import r2.lib.app_globals as _app_globals_mod
    _app_globals_mod.g = g

    # Expose config to the per-request context module.
    _r2_ctx.config.__dict__.update(config)

    if setup_globals:
        config['r2.import_private'] = \
            ConfigValue.bool(global_conf['import_private'])
        g.setup()
        g.plugins.declare_queues(g.queues)

    g.plugins.load_plugins(config)
    config['r2.plugins'] = g.plugins
    g.startup_timer.intermediate("plugins")

    config['r2.helpers'] = r2.lib.helpers

    # -----------------------------------------------------------------
    # Jinja2 template environment (replaces Mako)
    # -----------------------------------------------------------------
    template_dirs = paths['templates']
    # Plugins may contribute additional template directories
    for plugin in g.plugins:
        plugin_tmpl = getattr(plugin, 'template_dir', None)
        if plugin_tmpl and os.path.isdir(plugin_tmpl):
            template_dirs.append(plugin_tmpl)

    jinja_env = Environment(
        loader=FileSystemLoader(template_dirs),
        autoescape=select_autoescape(['html', 'xml']),
        extensions=['jinja2.ext.i18n'],
    )

    # Wire up i18n so {{ _("foo") }} works in templates
    from r2.lib.i18n import _, ungettext
    jinja_env.install_gettext_callables(_, ungettext, newstyle=True)

    g.jinja_env = jinja_env
    config['r2.jinja_env'] = jinja_env

    # -----------------------------------------------------------------
    # Routes map (kept for reference during incremental migration;
    # FastAPI routing defined in r2.main takes precedence at runtime)
    # -----------------------------------------------------------------
    from r2.config.routing import make_map
    config['routes.map'] = make_map(config)

    config['r2.response_options'] = {'headers': {}}

    if setup_globals:
        g.setup_complete()

    return config
