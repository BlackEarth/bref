import json
import os
from codecs import open

from setuptools import find_packages, setup

path = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(path, "README.rst"), encoding="utf-8") as f:
    read_me = f.read()

with open(os.path.join(path, "setup.json"), encoding="utf-8") as f:
    config = json.loads(f.read())

setup(
    long_description=read_me,
    packages=find_packages(exclude=["contrib", "docs", "tests*"]),
    **config
)
