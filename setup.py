from setuptools import setup

import re
import io
import os.path


def read(*names, **kwargs):
    with io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ) as fp:
        return fp.read()

def find_version(*file_paths):

    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='BBTornado',
    version=find_version('bbtornado', '__init__.py'),
    author='Tristan King',
    author_email='tristan.king@gmail.com',
    packages=['bbtornado', 'bbtornado.alembic'],
    url='http://github.com/bakkenbaeck/bbtornado',
    description='Basic app setup using tornado.',
    long_description=open('README.md').read(),
    install_requires=['tornado', 'futures', 'sqlalchemy', 'six', 'python-dateutil'],
    extras_require={
        'jsonschema': ['jsonschema']
    }
)
