"""Setup script for Sportify Widget"""

from setuptools import setup, find_packages

setup(
    name="sportify-widget",
    version="1.0.0",
    description="Desktop sports widget for live scores and standings",
    author="Muhammad Fawad Aleem",
    packages=find_packages(),
    install_requires=[
        "PyQt5>=5.15.9",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "sportify-widget=src.main:main",
        ],
    },
    python_requires=">=3.8",
)
