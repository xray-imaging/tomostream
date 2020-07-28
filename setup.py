from setuptools import setup, find_packages

setup(
    name='tomostream',
    version=open('VERSION').read().strip(),
    author='Viktor Nikitin, Francesco De Carlo',
    url='https://github.com/xray-imaging/tomostream',
    packages=find_packages(),
    include_package_data = True,
    scripts=['bin/tomostream'],
    description='cli to run streaming analysis of tomographic data',
    zip_safe=False,
)