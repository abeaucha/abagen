#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
from datetime import datetime
import os
import sys


# -- Project information -----------------------------------------------------

# Add project name, copyright holder, and author(s)
project = 'abagen'
author = '{} developers'.format(project)
copyright = '2018-{}, {}'.format(datetime.now().year, author)

# Import project to get version info
sys.path.insert(0, os.path.abspath(os.path.pardir))
import abagen  # noqa
# The short X.Y version
version = abagen.__version__
# The full version, including alpha/beta/rc tags
release = abagen.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.mathjax',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinxarg.ext',
]

# Generate the API documentation when building
autosummary_generate = True
autodoc_default_options = {'members': True, 'inherited-members': True}
numpydoc_show_class_members = False
autoclass_content = "class"

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
import sphinx_rtd_theme  # noqa
html_theme = 'sphinx_rtd_theme'
html_show_sourcelink = False

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'logo_only': True
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_logo = '_static/abagen_logo.svg'

# https://github.com/rtfd/sphinx_rtd_theme/issues/117
def setup(app):  # noqa
    app.add_css_file('theme_overrides.css')
    app.add_js_file('https://cdn.rawgit.com/chrisfilo/zenodo.js/v0.1/zenodo.js')  # noqa


# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'abagendoc'


# -- Extension configuration -------------------------------------------------
intersphinx_mapping = {
    'python': ('https://docs.python.org/3.7', None),
    'numpy': ('https://docs.scipy.org/doc/numpy', None),
    'pandas': ('https://pandas-docs.github.io/pandas-docs-travis/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/reference', None),
}

doctest_global_setup = """
import abagen
abagen.fetch_microarray(donors='all', verbose=0, n_proc=6)
atlas = abagen.fetch_desikan_killiany()

import pandas as pd
pd.set_option('display.width', 1000)
pd.set_option('max_rows', 6)
pd.set_option('max_columns', 6)
"""
