import os
from codecs import open

from setuptools import find_packages, setup

PACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(PACKAGE_PATH, "README.rst"), encoding="utf-8") as f:
    read_me = f.read()

setup(
    name="bref",
    version="0.7.0",
    description="Reference parsing and formatting library",
    long_description=read_me,
    url="https://github.com/BlackEarth/bref",
    author="Sean Harrison",
    author_email="sah@blackearthgroup.com",
    license="LGPL 3.0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Programming Language :: Python :: 3",
    ],
    install_requires=[
        "bl @ git+https://github.com/blackearth/bl.git@21fff5c2d8b4b303a43870477d0c8b1caeb9ba96#egg=bl",  # noqa
        "bxml @ git+https://github.com/BlackEarth/bxml.git@b58a3d3f9ac93d14cc50e63ccad094e73285099a#egg=bxml",  # noqa
        "lxml~=4.9.1",
    ],
    extras_require={
        "dev": [
            "black~=22.10.0",
            "flake8~=5.0.4",
            "ipython~=8.6.0",
            "isort~=5.10.1",
        ],
        "test": [
            "black~=22.10.0",
            "flake8~=5.0.4",
        ],
    },
    packages=find_packages(exclude=["contrib", "docs", "tests*"]),
    package_data={"bref": ["resources/canons/*.xml"]},
    data_files=[],
    entry_points={},
    scripts=[],
)
