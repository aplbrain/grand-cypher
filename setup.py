import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

["sqlalchemy"]

setuptools.setup(
    name="grand-cypher",
    version="0.1.1",
    author="Jordan Matelsky",
    author_email="opensource@matelsky.com",
    description="Query Grand graphs using Cypher",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aplbrain/grandcypher",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
