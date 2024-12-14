from setuptools import setup, find_packages

setup(
    name="comment_analyzer",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'pandas>=1.3.0',
        'aiohttp>=3.8.0',
        'tqdm>=4.65.0',
    ],
    entry_points={
        'console_scripts': [
            'comment_analyzer=main:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool for analyzing product comments and summarizing requirements",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    python_requires='>=3.7',
)