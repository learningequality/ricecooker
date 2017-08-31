#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ricecooker
from setuptools import setup, find_packages


try:
    import pypandoc
    readme = pypandoc.convert_file('README.md', 'rst')
except (IOError, ImportError):
    readme = open('README.md').read()

with open('docs/history.rst') as history_file:
    history = history_file.read()

requirements = [
    "pytest>=3.0.2",
    "requests>=2.11.1",
    "pillow>=3.3.1",
    "docopt>=0.6.2",
    "le_utils>=0.0.9rc24",
    "validators",
    "requests_file",
    "beautifulsoup4==4.5.1",
    "pressurecooker==0.0.15",
    "selenium==3.0.1",
    "youtube-dl",
    "html5lib",
    "cachecontrol==0.12.0",
    "lockfile==0.12.2",
    "css-html-js-minify==2.2.2",
    "websocket-client==0.40.0",
    "mock==2.0.0",
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='ricecooker',
    version=ricecooker.__version__,
    description="API for adding content to the Kolibri content curation server",
    long_description=readme + '\n\n' + history,
    author="Learning Equality",
    author_email='dev@learningequality.org',
    url='https://github.com/learningequality/ricecooker',
    packages=find_packages(),
    package_dir={'ricecooker':'ricecooker'},
    entry_points={},
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='ricecooker',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Education',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
