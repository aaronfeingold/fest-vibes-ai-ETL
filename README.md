# ajf-live-re-wire

## Overview
`ajf-live-re-wire` is a Python ETL Pipeline. It was designed initially to reorganize the WWOZ Livewire, a music calendar of events in New Orleans. Its main purpose now is analyze and evaluate local and-eventually-global music trends.

## Prerequisites
- Python 3.11.10
  - recommended: use `pyenv`
- `pipenv`
- postgres


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
### Test Suites
**Ensure the PYTHONPATH is set**
```sh
PYTHONPATH=. pytest tests/test_main.py
```

### Python Debugger
**Python: Select Interpreter**

- Press Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows/Linux)
- Type "Python: Select Interpreter"
- Look for the interpreter that points to your Pipenv virtual environment (it should be something like ~/.local/share/virtualenvs/your-project-name-xxxxx/bin/python)

**Run Python: Pipenv Debug with VSCode's Debugger tool**

### Docker Image
- Lambda Invocation:
```
# build and tag locally
docker build --target dev -t ajf-live-re-wire:dev .
# create new container from latest dev build
docker run \
  --network host \
  -v ~/.aws:/root/.aws \
  -e PG_DATABASE_URL=postgresql://{username}:{password}@localhost:{db_port}/{db_name} \
  -e BASE_URL="https://www.wwoz.org" \
  -e GOOGLE_MAPS_API_KEY=a_super_secret_thing \
  -e S3_BUCKET_NAME=your-data-bucket-name \
  # For local Redis:
  -e REDIS_URL=redis://localhost:6379 \
  # For Heroku Redis:
  # -e REDIS_URL=redis://username:password@hostname:port \
  ajf-live-re-wire:dev
```

#### Redis Configuration for Local Development

1. **Configure Redis to Accept External Connections**
   ```bash
   # Edit Redis configuration
   sudo nano /etc/redis/redis.conf
   
   # Find and modify the bind line to:
   bind 0.0.0.0
   
   # Restart Redis
   sudo systemctl restart redis
   ```

2. **Verify Redis is Running**
   ```bash
   # Check Redis status
   sudo systemctl status redis
   
   # Test Redis connection
   redis-cli ping
   ```

3. **Querying Redis Data**
   ```bash
   # Connect to Redis CLI
   redis-cli

   # List all keys (our events are stored with pattern "events:YYYY-MM-DD")
   KEYS "events:*"

   # Get a specific event date's data
   GET "events:2024-03-20"

   # Monitor Redis in real-time
   redis-cli monitor

   # Check Redis memory usage
   redis-cli info memory

   # Get all keys with their TTL (time to live)
   redis-cli --scan --pattern "events:*" | while read key; do echo "$key: $(redis-cli ttl "$key")"; done
   ```

4. **Debugging Redis Connection Issues**

   a. **From Host Machine:**
   ```bash
   # Test basic Redis connectivity
   redis-cli ping
   
   # Check Redis is listening on all interfaces
   netstat -tulpn | grep 6379
   ```

   b. **From Docker Container:**
   ```bash
   # Enter the container
   docker exec -it <container_id> bash
   
   # Test Redis connection using Python
   python3
   >>> import redis
   >>> r = redis.Redis(host='localhost', port=6379, decode_responses=True)
   >>> print(r.ping())  # Should return True
   ```

   c. **Common Issues:**
   - If `redis-cli` is not found in container: This is expected as we don't install it in the container
   - Connection refused: Check Redis is running and configured to accept external connections
   - Timeout: Verify network settings and firewall rules
   - Authentication error: Check if Redis password is required and properly configured

4. **Network Configuration**
   - Using `--network host` allows the container to access Redis on localhost
   - For non-host networking, use the host machine's IP address instead of localhost
   - Ensure no firewall rules are blocking Redis port (6379)

## Deployment
## Github Actions
The GitHub Actions workflow automates the deployment process to AWS Lambda. Here's what it does:

1. **Build and Test**
   - Runs on every push to main branch
   - Sets up Python 3.11 environment
   - Installs dependencies using pipenv
   - Runs pytest test suite
   - Builds Docker image for both development and production

2. **AWS Deployment**
   - Authenticates with AWS using GitHub Secrets
   - Logs into Amazon ECR (Elastic Container Registry)
   - Tags and pushes the Docker image to ECR
   - Updates the Lambda function with the new image

The workflow ensures consistent deployments and reduces manual intervention in the deployment process.

## Beta User Manual (Not Recommended)

- **build docker image**
```
docker build  --target prod -t ajf-live-re-wire .
```
- **login**
```
docker login -u AWS -p $(aws ecr get-login-password --region us-east-1) XXXXX.dkr.ecr.us-east-1.amazonaws.com/ajf-life-re-wire
```
- **tag**
```
docker tag $lambda_name:latest XXXXX.dkr.ecr.us-east-1.amazonaws.com/ajf-life-re-wire:latest
```
- **push to ECR**
```
docker push XXXXX.dkr.ecr.us-east-1.amazonaws.com/ajf-life-re-wire:latest
```
- **update lambda**
```
aws lambda update-function-code --function-name $lambda_name --image-uri XXXXX.dkr.ecr.us-east-1.amazonaws.com/ajf-life-re-wire:latest
```
