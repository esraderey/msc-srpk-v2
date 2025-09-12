from setuptools import setup, find_packages

setup(
    name="msc-srpk",
    version="2.0.0",
    author="Raúl Cruz Acosta",
    author_email="",
    description="MSC SRPK v2.0 - Grafo de Conocimiento de Código con embeddings y métricas de calidad",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://example.com/msc-srpk",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.9",
    install_requires=[
        "torch>=2.0.0",
        "transformers>=4.40.0",
        "numpy>=1.23.0",
        "pytest>=7.0.0",
    ],
    entry_points={
        "console_scripts": [
            "msc-srpk=msc_srpk.cli:main",
        ]
    },
)
