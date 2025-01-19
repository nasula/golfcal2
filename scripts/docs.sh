#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Track if any step failed
FAILED=0

# Ensure we're in virtual environment
#if [ -z "$VIRTUAL_ENV" ]; then
#    echo -e "${RED}Error: Virtual environment not activated. Please run:${NC}"
#    echo -e "${YELLOW}source venv/bin/activate${NC}"
#    exit 1
#fi

# Install Sphinx and extensions if not already installed
echo -e "${YELLOW}Installing documentation dependencies...${NC}"
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints || {
    echo -e "${RED}Failed to install Sphinx dependencies${NC}"
    exit 1
}

# Create docs directory structure if it doesn't exist
if [ ! -d "docs" ]; then
    echo -e "${YELLOW}Creating docs directory structure...${NC}"
    mkdir -p docs/api docs/_static docs/_templates
fi

# Initialize Sphinx if not already initialized
if [ ! -f "docs/conf.py" ]; then
    echo -e "${YELLOW}Initializing Sphinx...${NC}"
    cd docs
    sphinx-quickstart -q \
        --project="GolfCal2" \
        --author="GolfCal2 Team" \
        --sep \
        --ext-autodoc \
        --ext-viewcode \
        --ext-napoleon \
        -v 1.0 \
        -r 1.0 \
        -l en \
        --makefile \
        --batchfile
    cd ..
fi

# Update Sphinx configuration
echo -e "${YELLOW}Updating Sphinx configuration...${NC}"
cat > docs/conf.py << EOL
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
EOL

# Create index.rst if it doesn't exist
if [ ! -f "docs/index.rst" ]; then
    echo -e "${YELLOW}Creating documentation index...${NC}"
    cat > docs/index.rst << EOL
Welcome to GolfCal2's Documentation
=================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/services
   api/models
   api/utils

Services
--------
.. toctree::
   :maxdepth: 1

   api/services

Models
------
.. toctree::
   :maxdepth: 1

   api/models

Utilities
--------
.. toctree::
   :maxdepth: 1

   api/utils

Indices and Tables
==================

* :ref:\`genindex\`
* :ref:\`modindex\`
* :ref:\`search\`
EOL
fi

# Create API documentation files
echo -e "${YELLOW}Creating API documentation files...${NC}"

# Ensure api directory exists
mkdir -p docs/api

# Services documentation
cat > docs/api/services.rst << EOL
Services
========

Weather Services
--------------

.. automodule:: golfcal2.services.weather_service
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Calendar Services
---------------

.. automodule:: golfcal2.services.calendar_service
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Reservation Services
-----------------

.. automodule:: golfcal2.services.reservation_service
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
EOL

# Models documentation
cat > docs/api/models.rst << EOL
Models
======

.. automodule:: golfcal2.models
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
EOL

# Utils documentation
cat > docs/api/utils.rst << EOL
Utilities
========

.. automodule:: golfcal2.utils
   :members:
   :undoc-members:
   :show-inheritance:
EOL

# Build documentation
echo -e "${YELLOW}Building documentation...${NC}"
cd docs
if [ -f "Makefile" ]; then
    make html
else
    sphinx-build -b html . _build/html
fi
BUILD_STATUS=$?

if [ $BUILD_STATUS -eq 0 ]; then
    echo -e "\n${GREEN}✨ Documentation built successfully!${NC}"
    echo -e "Open ${YELLOW}docs/_build/html/index.html${NC} in your browser to view it"
else
    echo -e "\n${RED}❌ Documentation build failed${NC}"
    exit 1
fi 