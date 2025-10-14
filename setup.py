from setuptools import setup, find_packages

setup(
    name="epacomp_tox",
    version="0.1.0",
    description="Model Context Protocol (MCP) for EPA CompTox data",
    author="Manus",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "ctxpy",
    ],
    python_requires=">=3.7",
)
