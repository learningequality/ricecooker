#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ricecooker
from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('docs/history.rst') as history_file:
    history = history_file.read()

requirements = [
    'Click>=6.0',
    # TODO: put package requirements here
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
    packages=[
        'ricecooker',
    ],
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
