#!/usr/bin/env python3
"""
Enhanced ECR Build and Push Script
Integrates with existing deployment utilities for building and pushing Docker images
"""

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from shared.utils.version import get_project_name, get_version
except ImportError:
    print("Warning: Could not import version utilities.")

    def get_version():
        return "latest"

    def get_project_name():
        return "fest-vibes-ai-etl-pipeline"


# Import the existing deployment manager
try:
    from scripts.deployment_utils import DeploymentManager
except ImportError:
    print("Warning: Could not import DeploymentManager.")
    DeploymentManager = None


class DockerBuildManager:
    """Enhanced Docker build manager with ECR integration"""

    def __init__(
        self, aws_region: str = "us-east-1", aws_account_id: str = "937355130135"
    ):
        self.aws_region = aws_region
        self.aws_account_id = aws_account_id
        self.ecr_registry = f"{aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com"
        self.components = ["extractor", "loader", "cache_manager", "param_generator"]
        self.project_root = project_root

        # Initialize deployment manager if available
        self.deployment_manager = None
        if DeploymentManager:
            try:
                self.deployment_manager = DeploymentManager(aws_region)
            except Exception as e:
                print(f"Warning: Could not initialize DeploymentManager: {e}")

    def log_info(self, message: str):
        """Log info message with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [INFO] {message}")

    def log_success(self, message: str):
        """Log success message"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [SUCCESS] ✓ {message}")

    def log_error(self, message: str):
        """Log error message"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [ERROR] ✗ {message}")

    def log_warning(self, message: str):
        """Log warning message"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [WARNING] ⚠ {message}")

    def check_prerequisites(self) -> bool:
        """Check if Docker and AWS CLI are available"""
        try:
            # Check Docker
            subprocess.run(["docker", "info"], capture_output=True, check=True)
            self.log_success("Docker is running")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_error("Docker is not running or not installed")
            return False

        try:
            # Check AWS CLI
            subprocess.run(["aws", "--version"], capture_output=True, check=True)
            self.log_success("AWS CLI is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_error("AWS CLI is not installed")
            return False

        return True

    def ecr_login(self) -> bool:
        """Authenticate with ECR"""
        self.log_info(f"Authenticating with ECR registry: {self.ecr_registry}")

        try:
            # Get ECR login token
            get_token_cmd = [
                "aws",
                "ecr",
                "get-login-password",
                "--region",
                self.aws_region,
            ]
            token_result = subprocess.run(
                get_token_cmd, capture_output=True, text=True, check=True
            )

            # Docker login
            login_cmd = [
                "docker",
                "login",
                "--username",
                "AWS",
                "--password-stdin",
                self.ecr_registry,
            ]
            subprocess.run(login_cmd, input=token_result.stdout, text=True, check=True)

            self.log_success("ECR authentication successful")
            return True

        except subprocess.CalledProcessError as e:
            self.log_error(f"ECR authentication failed: {e}")
            return False

    def get_image_tags(self, custom_tag: Optional[str] = None) -> List[str]:
        """Generate image tags for the build"""
        tags = ["latest"]

        if custom_tag:
            tags.append(custom_tag)
        else:
            version = get_version()
            if version != "latest":
                tags.append(version)

        # Add git commit hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            commit_hash = result.stdout.strip()
            if commit_hash and commit_hash not in tags:
                tags.append(commit_hash)
        except subprocess.CalledProcessError:
            pass

        # Add timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        tags.append(timestamp)

        return tags

    def build_component(
        self, component: str, tags: List[str], verbose: bool = False
    ) -> bool:
        """Build a single component with multiple tags"""
        self.log_info(f"Building component: {component}")

        dockerfile_path = self.project_root / "src" / component / "Dockerfile"
        if not dockerfile_path.exists():
            self.log_error(f"Dockerfile not found: {dockerfile_path}")
            return False

        # Build with primary tag
        primary_tag = tags[0]
        image_name = f"{self.ecr_registry}/fest-vibes-ai-{component}:{primary_tag}"

        build_cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(dockerfile_path),
            str(self.project_root),
        ]

        try:
            if verbose:
                subprocess.run(build_cmd, check=True)
            else:
                subprocess.run(build_cmd, capture_output=True, check=True)

            # Tag with additional tags
            for tag in tags[1:]:
                additional_image = (
                    f"{self.ecr_registry}/fest-vibes-ai-{component}:{tag}"
                )
                subprocess.run(
                    ["docker", "tag", image_name, additional_image], check=True
                )

            self.log_success(f"Built {component} with tags: {', '.join(tags)}")
            return True

        except subprocess.CalledProcessError as e:
            self.log_error(f"Failed to build {component}: {e}")
            return False

    def push_component(
        self, component: str, tags: List[str], verbose: bool = False
    ) -> bool:
        """Push a component with all its tags"""
        self.log_info(f"Pushing component: {component}")

        try:
            for tag in tags:
                image_name = f"{self.ecr_registry}/fest-vibes-ai-{component}:{tag}"
                if verbose:
                    subprocess.run(["docker", "push", image_name], check=True)
                else:
                    subprocess.run(
                        ["docker", "push", image_name], capture_output=True, check=True
                    )

            self.log_success(f"Pushed {component} with all tags")
            return True

        except subprocess.CalledProcessError as e:
            self.log_error(f"Failed to push {component}: {e}")
            return False

    def build_and_push_component(
        self, component: str, tags: List[str], verbose: bool = False
    ) -> bool:
        """Build and push a single component (for parallel execution)"""
        success = self.build_component(component, tags, verbose)
        if success:
            success = self.push_component(component, tags, verbose)
        return success

    def build_and_push_parallel(
        self, components: List[str], tags: List[str], verbose: bool = False
    ) -> bool:
        """Build and push components in parallel"""
        self.log_info(f"Building {len(components)} components in parallel")

        threads = []
        results = {}

        def worker(component):
            results[component] = self.build_and_push_component(component, tags, verbose)

        # Start threads
        for component in components:
            thread = threading.Thread(target=worker, args=(component,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        failed_components = [comp for comp, success in results.items() if not success]
        if failed_components:
            self.log_error(f"Failed to build/push: {', '.join(failed_components)}")
            return False

        self.log_success("All components built and pushed successfully")
        return True

    def build_and_push_sequential(
        self, components: List[str], tags: List[str], verbose: bool = False
    ) -> bool:
        """Build and push components sequentially"""
        for component in components:
            if not self.build_and_push_component(component, tags, verbose):
                return False

        self.log_success("All components built and pushed successfully")
        return True

    def run_terraform(self, image_tag: str, dry_run: bool = False) -> bool:
        """Run terraform apply using the deployment manager"""
        if not self.deployment_manager:
            self.log_warning("DeploymentManager not available, skipping terraform")
            return True

        self.log_info(
            f"Running Terraform {'plan' if dry_run else 'apply'} with tag: {image_tag}"
        )

        try:
            success = self.deployment_manager.deploy_by_tag(image_tag, dry_run)
            if success:
                action = "planned" if dry_run else "deployed"
                self.log_success(f"Terraform {action} successfully")
            return success
        except Exception as e:
            self.log_error(f"Terraform execution failed: {e}")
            return False

    def show_build_summary(self, components: List[str], tags: List[str]):
        """Show build summary"""
        print("\n" + "=" * 60)
        print("BUILD SUMMARY")
        print("=" * 60)
        print(f"Project: {get_project_name()}")
        print(f"Version: {get_version()}")
        print(f"Registry: {self.ecr_registry}")
        print(f"Components: {', '.join(components)}")
        print(f"Tags: {', '.join(tags)}")
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Enhanced ECR build and push script")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--account-id", default="937355130135", help="AWS account ID")
    parser.add_argument("--tag", help="Custom tag for images")
    parser.add_argument("--components", help="Comma-separated list of components")
    parser.add_argument("--parallel", action="store_true", help="Build in parallel")
    parser.add_argument(
        "--terraform", action="store_true", help="Run terraform after build"
    )
    parser.add_argument(
        "--terraform-dry-run", action="store_true", help="Run terraform plan only"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--skip-build", action="store_true", help="Skip build, only run terraform"
    )

    args = parser.parse_args()

    # Initialize build manager
    builder = DockerBuildManager(args.region, args.account_id)

    # Determine components to build
    if args.components:
        components = [comp.strip() for comp in args.components.split(",")]
    else:
        components = builder.components

    # Get image tags
    tags = builder.get_image_tags(args.tag)

    # Show build summary
    builder.show_build_summary(components, tags)

    # Skip build if requested
    if args.skip_build:
        builder.log_info("Skipping build phase")
    else:
        # Check prerequisites
        if not builder.check_prerequisites():
            sys.exit(1)

        # ECR login
        if not builder.ecr_login():
            sys.exit(1)

        # Build and push
        if args.parallel:
            success = builder.build_and_push_parallel(components, tags, args.verbose)
        else:
            success = builder.build_and_push_sequential(components, tags, args.verbose)

        if not success:
            sys.exit(1)

    # Run terraform if requested
    if args.terraform or args.terraform_dry_run:
        primary_tag = args.tag if args.tag else get_version()
        if not builder.run_terraform(primary_tag, args.terraform_dry_run):
            sys.exit(1)

    builder.log_success("Build and push process completed successfully!")


if __name__ == "__main__":
    main()
