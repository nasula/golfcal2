from setuptools import setup, find_packages

setup(
    name="golfcal2",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"golfcal2": ["py.typed"]},
    install_requires=[
        'openmeteo-requests>=1.1.0',
        'requests-cache>=1.1.0',
        'retry-requests>=2.0.0',
        'pandas>=2.0.0'
    ],
    entry_points={
        'console_scripts': [
            'golfcal2=golfcal2.cli:main',
            'golfcal2-service=golfcal2_service:main'
        ]
    }
) 