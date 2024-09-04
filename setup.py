"""The don't-repeat-yourself Python metaprogramming library."""


classifiers = """\
Development Status :: 3 - Alpha
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: Python :: 3.4
Topic :: Software Development :: Libraries
"""


from distutils.core import setup


with open("README.md") as readme:
    readme = readme.read()


setup(
    name='drython',
    version='0.1',
    packages=['drython'],
    url='url?',
    license='http://www.apache.org/licenses/LICENSE-2.0',
    author='Matthew Egan Odendahl',
    author_email='email?',
    description=__doc__,
    long_description=readme,
)


__doc__ += "\n\n" + readme

