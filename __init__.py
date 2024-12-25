"""
Golf calendar application package.
"""

__package__ = 'golfcal2'
__version__ = '1.0.0'

def verify_package():
    """Verify that we're running under the correct package."""
    import sys
    module = sys.modules[__name__]
    if module.__package__ != 'golfcal2':
        raise ImportError(f"Package is running as '{module.__package__}' instead of 'golfcal2'")
    return True
