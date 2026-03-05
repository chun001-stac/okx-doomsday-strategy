from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="okx-doomsday-strategy",
    version="2.0.0",
    author="OKX Doomsday Strategy Contributors",
    author_email="your.email@example.com",
    description="Optimized ETH-USDT perpetual contract trading strategy with ML integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/okx-doomsday-strategy",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "doomsday-trade=src.strategies.okx_doomsday_optimized_v2_ml_integrated:main",
            "doomsday-backtest=tools.backtest_doomsday_optimized:main",
            "doomsday-tune=tools.parameter_tuning:main",
        ],
    },
    include_package_data=True,
    package_data={
        "src.config": ["*.ini"],
    },
    keywords="trading, cryptocurrency, okx, strategy, algorithm, machine-learning",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/okx-doomsday-strategy/issues",
        "Source": "https://github.com/yourusername/okx-doomsday-strategy",
        "Documentation": "https://github.com/yourusername/okx-doomsday-strategy/wiki",
    },
)