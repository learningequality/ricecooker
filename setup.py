#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup

import ricecooker


readme = open('README.md').read()

with open('docs/history.rst') as history_file:
    history = history_file.read()

requirements = [
    "pytest>=3.0.2",
    "requests>=2.11.1",
    "le_utils>=0.1.26",
    "validators",                             # TODO: check if this is necessary
    "requests_file",
    "beautifulsoup4>=4.6.3,<4.9.0",   # pinned to match versions in le-pycaption
    "pressurecooker>=0.0.30",
    "selenium==3.0.1",
    "youtube-dl>=2020.6.16.1",
    "html5lib",
    "cachecontrol==0.12.0",
    "lockfile==0.12.2",                       # TODO: check if this is necessary
    "css-html-js-minify==2.2.2",
    "mock==2.0.0",
    "pypdf2>=1.26.0",
    "dictdiffer>=0.8.0",
    "Pillow==5.4.1",
    "colorlog>=4.1.0,<4.2",
    "PyYAML>=5.3.1",
    "Jinja2>=2.10"
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='ricecooker',
    version=ricecooker.__version__,
    description="API for adding content to the Kolibri content curation server",
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',
    author="Learning Equality",
    author_email='dev@learningequality.org',
    url='https://github.com/learningequality/ricecooker',
    packages=find_packages(),
    package_dir={'ricecooker':'ricecooker'},
    entry_points = {
        'console_scripts': [
            'corrections = ricecooker.utils.corrections:correctionsmain',
            'jiro = ricecooker.cli:main'
        ],
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='ricecooker',
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Natural Language :: English',
        'Topic :: Education',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
