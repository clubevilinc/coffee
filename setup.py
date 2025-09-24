# setup.py
from os import system
from setuptools import setup, find_packages

setup(
    name="coffee-terminal",
    version="1.0.0",
    description="Coffee AI Terminal Assistant",
    author="chai",
    author_email="boss@evilinc.in",
    packages=find_packages(include=["coffee", "coffee.*"]),
    install_requires=[
        "typer[all]>=0.9.0",
        "rich>=13.0.0",
        "groq>=0.4.0",
    ],
    entry_points={
        "console_scripts": [
            "coffee=coffee.main:app",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)

