#!/usr/bin/env python
from setuptools import setup
import sys

lxml_requirement = "lxml"
if sys.platform == 'darwin':
    import platform

    mac_ver = platform.mac_ver()[0]
    if mac_ver < '10.9':
        print("Using lxml<2.4")
        lxml_requirement = "lxml<2.4"

setup(
    name="wanish",
    version="0.6.0",
    author="Igor Gorschal",
    author_email="gorschal@gmail.com",
    description="open source implementation of summly",
    long_description=open("README.rst").read(),
    license="MIT",
    url="https://github.com/reefeed/wanish",
    packages=['wanish'],
    keywords=[
        "summly",
        "bookie",
        "content",
        "HTML",
        "parsing",
        "readability",
        "readable",
    ],
    install_requires=[
        "chardet",
        "requests",
        "cssselect",
        "numpy",
        "snowballstemmer",
        "networkx",
        "segtok",
        lxml_requirement
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Pre-processors",
        "Topic :: Text Processing :: Filters",
        "Topic :: Text Processing :: Markup :: HTML",
    ],
)
