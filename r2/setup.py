#!/usr/bin/env python
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
import fnmatch
import sys
from setuptools import setup, find_packages, Extension


commands = {}


try:
    from Cython.Build import cythonize
except ImportError:
    print("Cannot find Cython. Skipping Cython build.")
    pyx_extensions = []
else:
    pyx_files = []
    for root, directories, files in os.walk('.'):
        for f in fnmatch.filter(files, '*.pyx'):
            pyx_files.append(os.path.join(root, f))
    pyx_extensions = cythonize(pyx_files)


# guard against import errors in case this is the first run of setup.py and we
# don't have any dependencies (including baseplate) yet
try:
    from baseplate.integration.thrift.command import ThriftBuildPyCommand
except ImportError:
    print("Cannot find Baseplate. Skipping Thrift build.")
else:
    commands["build_py"] = ThriftBuildPyCommand


setup(
    name="r2",
    version="",
    python_requires=">=3.10",
    install_requires=[
        # --- Framework (Phase 4: replace Pylons with FastAPI) ---
        # "Pylons",          # Python 2 only; replaced by FastAPI in Phase 4
        # "Routes",          # replaced by FastAPI routing in Phase 4
        # "WebOb",           # replaced by Starlette/FastAPI in Phase 4
        "fastapi>=0.110",
        "uvicorn[standard]>=0.27",
        "python-multipart",  # form data parsing for FastAPI
        "starlette>=0.36",

        # --- Templates (Phase 5: replace Mako with Jinja2) ---
        # "mako>=0.5",       # replaced by Jinja2 in Phase 5
        "jinja2>=3.0",

        # --- Database / ORM ---
        "SQLAlchemy>=1.4",
        "psycopg2>=2.9",

        # --- Cassandra (TODO: migrate pycassa API -> cassandra-driver API) ---
        # "pycassa>=1.7.0",  # Python 2 only; cassandra-driver is the Py3 replacement
        #                      API is incompatible — requires adapter work after Phase 4
        "cassandra-driver>=3.25",

        # --- Caching ---
        "pylibmc>=1.6.1",    # was pinned to 1.2.2; 1.6+ has Python 3 support

        # --- AMQP (TODO: migrate amqplib API -> pika API) ---
        # "amqplib",         # Python 2 only
        "pika>=1.3",         # Python 3 AMQP client; API differs from amqplib

        # --- Cryptography ---
        # "pycrypto",        # deprecated; pycryptodome (below) covers everything
        "pycryptodome>=3.18",

        # --- Auth ---
        "bcrypt>=4.0",       # replaces py-bcrypt (same API, maintained)

        # --- AWS ---
        "boto3>=1.26",       # replaces boto 2.x (boto3 is the current SDK)

        # --- Web / HTTP ---
        "requests>=2.28",
        "httpx>=0.27",       # async HTTP client for FastAPI testing

        # --- Content / Parsing ---
        "beautifulsoup4>=4.12",   # replaces BeautifulSoup (old py2 package)
        "chardet>=5.0",
        "lxml>=4.9",
        "Pillow>=10.0",
        "tinycss2>=1.2",
        "l2cs>=2.0.2",

        # --- Markdown ---
        # snudown (Reddit C extension) replaced by mistune (pure Python, Py3 native)
        "mistune>=3.0",

        # --- CAPTCHA ---
        # PyCAPTCHA (C extension) replaced by Pillow-based generation (see r2/r2/lib/captcha.py)

        # --- Other services ---
        "kazoo>=2.9",        # Zookeeper client (already Py3 compatible)
        "stripe>=5.0",
        "pytz>=2023.3",
        "Babel>=2.12",
        "unidecode>=1.3",
        "PyYAML>=6.0",
        "python-snappy>=0.6",
        "httpagentparser>=1.9",  # was pinned to 1.7.8
        "sentry-sdk>=1.38",      # replaces raven (raven is EOL; sentry-sdk is the successor)
        "ndg-httpsclient>=0.5",
        "cython>=3.0",

        # --- i18n ---
        "Babel>=2.12",
    ],
    # setup tests
    tests_require=['pytest>=7.0', 'coverage', 'httpx'],
    dependency_links=[],
    packages=find_packages(exclude=["ez_setup"]),
    cmdclass=commands,
    ext_modules=pyx_extensions + [
        Extension(
            "Cfilters",
            sources=[
                "r2/lib/c/filters.c",
            ]
        ),
    ],
    entry_points="""
    [r2.provider.media]
    s3 = r2.lib.providers.media.s3:S3MediaProvider
    filesystem = r2.lib.providers.media.filesystem:FileSystemMediaProvider
    [r2.provider.cdn]
    fastly = r2.lib.providers.cdn.fastly:FastlyCdnProvider
    cloudflare = r2.lib.providers.cdn.cloudflare:CloudFlareCdnProvider
    null = r2.lib.providers.cdn.null:NullCdnProvider
    [r2.provider.auth]
    cookie = r2.lib.providers.auth.cookie:CookieAuthenticationProvider
    http = r2.lib.providers.auth.http:HttpAuthenticationProvider
    [r2.provider.support]
    zendesk = r2.lib.providers.support.zendesk:ZenDeskProvider
    [r2.provider.search]
    cloudsearch = r2.lib.providers.search.cloudsearch:CloudSearchProvider
    solr = r2.lib.providers.search.solr:SolrSearchProvider
    [r2.provider.image_resizing]
    imgix = r2.lib.providers.image_resizing.imgix:ImgixImageResizingProvider
    no_op = r2.lib.providers.image_resizing.no_op:NoOpImageResizingProvider
    unsplashit = r2.lib.providers.image_resizing.unsplashit:UnsplashitImageResizingProvider
    [r2.provider.email]
    null = r2.lib.providers.email.null:NullEmailProvider
    mailgun = r2.lib.providers.email.mailgun:MailgunEmailProvider
    """,
)
