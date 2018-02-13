
from setuptools import setup
from sys import version_info

if version_info < (3, 4):
    raise SystemExit('Sorry! responds requires python 3.4 or later.')

setup(
    name='responds',
    description='responds - async http framework',
    long_description='A miniature web framework for Python, using curio.',
    license='MIT',
    author='Aurieh',
    url='https://github.com/quiribot/responds',
    packages=['responds'],
    install_requires=['h11', 'curio'],
    classifiers=['Programming Language :: Python :: 3']
)
