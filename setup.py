from setuptools import setup, find_packages

setup(
    name='pylogchop',
    version='0.0.6',
    description='Log file to syslog shipper',
    long_description="""
Parses Logfiles, and creates a JSON representation, that is send to syslog

Copyright (c) 2016, Stephan Schultchen.

License: MIT (see LICENSE for details)
    """,
    packages=find_packages(),
    scripts=[
        'contrib/pylogchop',
    ],
    url='https://github.com/schlitzered/pylogchop',
    license='MIT',
    author='schlitzer',
    author_email='stephan.schultchen@gmail.com',
    test_suite='test',
    platforms='posix',
    classifiers=[
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3'
    ],
    install_requires=[
        'jsonschema',
        'pep3143daemon',
    ],
    keywords=[
    ]
)
