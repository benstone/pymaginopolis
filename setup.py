from setuptools import setup

setup(
    name='pymaginopolis',
    version='0.2.0',
    packages=[
        "pymaginopolis",
        "pymaginopolis.chunkyfile",
        "pymaginopolis.scriptengine",
        "pymaginopolis.tools"
    ],
    package_data={
        'pymaginopolis.scriptengine': [
            'data/opcodes.xml',
            'data/constants.xml'
        ],
    },
    url='https://github.com/benstone/pymaginopolis',
    license='MIT',
    author='Ben Stone',
    author_email='',
    description='Python utilities for reverse engineering Microsoft 3D Movie Maker',
    install_requires=[
        'setuptools'
    ]
)
