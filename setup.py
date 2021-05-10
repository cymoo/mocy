import io
from setuptools import setup
import slim

with io.open('README.md', 'rt') as f:
    readme = f.read()

setup(
    name='slim',
    version=slim.__version__,
    url='https://github.com/cymoo/slim',
    description='A light weight spider framework.',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='cymoo',
    author_email='wakenee@hotmail.com',
    license='MIT',
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Utilities',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='scrapy crawler spider',
    packages=['slim'],
    python_requires='>=3.6',
    install_requires=[
        'requests>=2.25.1',
        'beautifulsoup4>=4.9.3'
    ],
    extras_require={'dev': ['pytest']},
)
