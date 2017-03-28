#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ricecooker
from setuptools import setup, find_packages


with open('README.md') as readme_file:
    readme = readme_file.read()

with open('docs/history.rst') as history_file:
    history = history_file.read()

requirements = [
    "Click>=6.0",
    "pytest>=3.0.2",
    "requests>=2.11.1",
    "pillow>=3.3.1",
    "docopt>=0.6.2",
    "le_utils==0.0.9rc18",
    "validators",
    "requests_file",
    "beautifulsoup4==4.5.1",
    "pressurecooker==0.0.11",
    "selenium==3.0.1",
    "youtube-dl",
    "html5lib",
    "cachecontrol==0.12.0",
    "lockfile==0.12.2",
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='ricecooker',
    version=ricecooker.__version__,
    description="API for adding content to content curation server",
    long_description=readme + '\n\n' + history,
    author="Learning Equality",
    author_email='dev@learningequality.org',
    url='https://github.com/learningequality/ricecooker',
    packages=find_packages(),
    package_dir={'ricecooker':
                 'ricecooker'},
    entry_points={
        'console_scripts': [
            'ricecooker=ricecooker.cli:main'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='ricecooker',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
