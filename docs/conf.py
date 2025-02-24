import os
import sys


sys.path.insert(0, os.path.abspath('..'))

project = 'GolfCal2'
copyright = '2024, GolfCal2 Team'
author = 'GolfCal2 Team'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
]

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
templates_path = ['_templates']

# Autodoc settings
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autodoc_typehints_format = 'short'
autoclass_content = 'both'
autodoc_class_signature = 'mixed'
autodoc_preserve_defaults = True

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
