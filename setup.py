<<<<<<< HEAD
=======
"""This is the main entry point for building orthorec.
The setup process for orthorec is very much like any python module except
that the compilation of the the extension module(s) is driven by CMake through
scikit-build. Scikit-build defines a custom Extension class which calls CMake
and provides some common (for Python) CMake package finders.
You can pass build options to CMake using the normal -DBUILD_OPTION=something
syntax, but these options must separated from the setuptools options with two
dashes (--). For example, we can pass the EXTENSION_WRAPPER option as follows:
$ python setup.py build -- -DEXTENSION_WRAPPER=swig
For skbuild >= 0.10.0, the two dashes will not be required. See the top-level
CMakeLists.txt for the curent list of build options.
"""
# from skbuild import setup
>>>>>>> 0912478e6c7a8f476b9465dda95c998c18e8ccef
from setuptools import setup, find_packages

setup(
    name='tomostream',
    version=open('VERSION').read().strip(),
<<<<<<< HEAD
    author='Viktor Nikitin, Francesco De Carlo',
=======
    author='Viktor Nikitin',
    # package_dir={"": "src"},
>>>>>>> 0912478e6c7a8f476b9465dda95c998c18e8ccef
    url='https://github.com/xray-imaging/tomostream',
    packages=find_packages(),
    include_package_data = True,
    scripts=['bin/tomostream'],
    description='cli to run streaming analysis of tomographic data',
    zip_safe=False,
)