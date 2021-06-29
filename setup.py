import os
from setuptools import setup

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='tech-inventory-update',
    version='0.1',
    author="UW-IT AXDD",
    author_email="aca-it@uw.edu",
    install_requires=[
        'requests',
        'gspread',
        'PyYAML',
        'toml',
    ],
    license='Apache License, Version 2.0',
    description=('AXDD Technology spreadsheet updater'),
    url='https://github.com/uw-it-aca/tech-inventory-update',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
    ],
)
