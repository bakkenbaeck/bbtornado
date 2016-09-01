from setuptools import setup

setup(
    name='BBTornado',
    version='0.0.4',
    author='Tristan King',
    author_email='tristan.king@gmail.com',
    packages=['bbtornado', 'bbtornado.alembic'],
    url='http://github.com/bakkenbaeck/bbtornado',
    description='Basic app setup using tornado.',
    long_description=open('README.md').read(),
    install_requires = [ 'tornado==4.2.1','futures','sqlalchemy' ]
)
