import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="grand-cypher",
    version="0.9.0",
    author="Jordan Matelsky",
    author_email="opensource@matelsky.com",
    description="Query Grand graphs using Cypher",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aplbrain/grandcypher",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "grandiso",
        "lark-parser",
        "networkx",
    ],
)
