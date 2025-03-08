#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup

import ricecooker


readme = open("README.md").read()

with open("docs/history.rst") as history_file:
    history = history_file.read()

setup(
    name="ricecooker",
    version=ricecooker.__version__,
    description="API for adding content to the Kolibri content curation server",
    long_description=readme + "\n\n" + history,
    long_description_content_type="text/markdown",
    author="Learning Equality",
    author_email="dev@learningequality.org",
    url="https://github.com/learningequality/ricecooker",
    packages=find_packages(),
    package_dir={"ricecooker": "ricecooker"},
    entry_points={
        "console_scripts": [
            "corrections = ricecooker.utils.corrections:correctionsmain",
        ]
    },
    include_package_data=True,
    install_requires=[
        "requests>=2.11.1",
        "le_utils>=0.1.26",
        "requests_file",
        "beautifulsoup4>=4.6.3,<4.9.0",  # pinned to match versions in le-pycaption
        "selenium==4.31.0",
        "yt-dlp>=2024.12.23",
        "html5lib",
        "cachecontrol==0.14.2",
        "filelock==3.18.0",  # This is needed, but not specified as a dependency by cachecontrol
        "css-html-js-minify==2.5.5",
        "pypdf2==1.26.0",
        "dictdiffer>=0.8.0",
        "Pillow==11.1.0",
        "colorlog>=4.1.0,<6.9",
        "chardet==5.2.0",
        "ffmpy>=0.2.2",
        "pdf2image==1.17.0",
        "le-pycaption>=2.2.0a1",
        "EbookLib>=0.17.1",
        "filetype>=1.1.0",
        "urllib3==2.4.0",
    ],
    extras_require={
        "test": [
            "requests-cache==1.2.1",
            "pytest==8.3.5",
            "pycountry==24.6.1",
            "pytest-env==1.1.5",
            "vcrpy==7.0.0; python_version >='3.10'",
            "mock==5.2.0",
        ],
        "dev": [
            "pre-commit>=4.1.0",
        ],
    },
    python_requires=">=3.9, <3.13",
    license="MIT license",
    zip_safe=False,
    keywords="ricecooker",
    classifiers=[
        "Intended Audience :: Developers",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Natural Language :: English",
        "Topic :: Education",
    ],
    test_suite="tests",
)
