from setuptools import find_packages, setup


setup(
    name="easyai-client",
    version="0.1.0",
    description="EasyAI user client.",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "PyYAML>=6.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "easyai=pyai_assistant.cli.client:main",
        ]
    },
)
