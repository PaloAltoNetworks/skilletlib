import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="skilletlib",
    version="0.4.1",
    author="Nathan Embery",
    author_email="nembery@paloaltonetworks.com",
    description="Tools for working with PAN-OS Skillets in Python 3",
    license='Apache 2.0',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/paloaltonetworks/skilletlib",
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={'assets': ['skilletlib/assets/**/*.yaml', 'skilletlib/assets/**/*.xml']},
    install_requires=[
        "oyaml",
        "docker",
        "pan-python",
        "pathlib",
        "jinja2",
        "pyyaml",
        "xmldiff",
        "xmltodict",
        "requests-toolbelt",
        "requests",
        "jsonpath_ng",
        "passlib",
        "GitPython",
        "jinja2-ansible-filters"
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    python_requires='>=3.6',
)
