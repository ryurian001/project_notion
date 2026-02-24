from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="lablogger",
    version="0.1.0",
    author="rianryu001",
    author_email="rwj1203@naver.com",
    description="A simple experiment logger for ML/DL projects with JSON-formatted logging",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ryurian001/project_notion",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    keywords="logging experiment logger machine-learning deep-learning",
)
