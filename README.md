# ajf-live-re-wire

## Overview
`ajf-live-re-wire` is a Python project designed to reorganize the WWOZ Livewire. It uses web scraping to gather and process data from the WWOZ Livewire website.

## Prerequisites
- Python 3.11.10
  - recommended: use `pyenv`
- `pipenv`


## Installation

### Recommended: `pyenv`
- `pyenv` is a simple, powerful tool for managing multiple versions of Python. Follow the instructions below to install `pyenv` on your system.
- Check out [this project](https://github.com/aaronfeingold/ajf-fedora-workstation-ansible?tab=readme-ov-file#fedora-workstation-ansible) for an automated installation via Ansible.

#### Linux:
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

#### Install Python 3.11.10 using `pyenv`
```sh
pyenv install 3.11.10
pyenv global 3.11.10
```

### Install `pipenv`
- `pipenv` is a tool that aims to bring the best of all packaging worlds (bundled, development, and deployment) to the Python world. It automatically creates and manages a virtual environment for your projects, as well as adds/removes packages from your Pipfile as you install/uninstall packages.

```sh
pip install pipenv
```

### Clone the Repository
```sh
git clone https://github.com/aaronfeingold/ajf-live-re-wire.git
cd ajf-live-re-wire
```

## Usage

### Activate the Pipenv Shell
```sh
pipenv shell
```

### Install Dependencies
```sh
pipenv install
```

### Run
```sh
python main.py
```

## Testing
**Ensure the PYTHONPATH is set**
```sh
PYTHONPATH=. pytest tests/test_main.py
```


# Deployment
- TBD: Github Pipeline Under Construction

## Beta User Manual

```
cd CICD
chmod +x scripts/build_and_update_lambda
./scripts/build_and_deploy
```
