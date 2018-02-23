from sys import version_info

from setuptools import setup

# We only use 3.5 features
# but curio requires >= 3.6
if version_info < (3, 6):
    raise SystemExit('Sorry! responds requires python 3.6 or later.')

setup(
    name='responds',
    description='responds - async http framework',
    long_description='A web framework for Python, using curio.',
    license='LGPL',
    author='Aurieh',
    url='https://github.com/quiribot/responds',
    packages=['responds', 'responds.backends'],
    install_requires=['httptools', 'curio', 'werkzeug'],
    classifiers=['Programming Language :: Python :: 3']
)
