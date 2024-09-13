# oz-re-wire

## Overview
`oz-re-wire` is a Python project designed to reorganize the WWOZ Livewire. It uses web scraping to gather and process data from the WWOZ Livewire website.

## Prerequisites
- Python 3.11
- `pyenv`
- `pipenv`

## Installation

### Step 1: Install `pyenv`
`pyenv` is a simple, powerful tool for managing multiple versions of Python. Follow the instructions below to install `pyenv` on your system.

#### On Linux:
```sh
# Install dependencies
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev \
python-openssl git

# Install pyenv
curl https://pyenv.run | bash

# Add pyenv to bash so that it loads every time you open a terminal
echo -e '\n# Pyenv Configuration' >> ~/.bashrc
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
source ~/.bashrc
```


### Step 3: Install Python 3.11 using `pyenv`
```sh
pyenv install 3.11.0
pyenv global 3.11.0
```

### Step 4: Install pipenv
`pipenv` is a tool that aims to bring the best of all packaging worlds (bundled, development, and deployment) to the Python world. It automatically creates and manages a virtual environment for your projects, as well as adds/removes packages from your Pipfile as you install/uninstall packages.

```sh
pip install pipenv
```

### Step 5: Install Dependencies
```sh
pipenv install
```
### Step 6: Clone the Repository
```sh
git clone https://github.com/yourusername/oz-re-wire.git
cd oz-re-wire
```
## Usage

### Step 1: Activate the Pipenv Shell
```sh
pipenv shell
```

### Step 2: Run the Application
```sh
python main.py
```
