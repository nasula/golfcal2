from setuptools import setup, find_packages

setup(
    name="golfcal2",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "icalendar",
        "pytz",
        "python-dateutil",
        "pyyaml",
    ],
    entry_points={
        'console_scripts': [
            'golfcal2=golfcal2.cli:main',
        ],
    },
) 