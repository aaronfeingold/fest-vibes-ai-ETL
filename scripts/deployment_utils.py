#!/usr/bin/env python3
"""
Simple deployment utilities for managing versions and deployments
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from shared.utils.version import get_project_name, get_version  # type: ignore
except ImportError:
    print("Warning: Could not import version utilities.")

    def get_version():
        return "unknown"

    def get_project_name():
        return "fest-vibes-ai-etl-pipeline"


class DeploymentManager:
    """Simple deployment manager for the ETL pipeline"""

    def __init__(self, aws_region: str = "us-east-1"):
        self.aws_region = aws_region
        self.components = ["extractor", "loader", "cache_manager", "param_generator"]
        self.ecr_repositories = [f"fest-vibes-ai-{comp}" for comp in self.components]

        try:
            self.ecr_client = boto3.client("ecr", region_name=aws_region)
        except Exception as e:
            print(f"Warning: Could not initialize AWS ECR client: {e}")
            self.ecr_client = None

    def list_git_tags(self):
        """List Git version tags"""
        try:
            result = subprocess.run(
                ["git", "tag", "-l", "v*"], capture_output=True, text=True, check=True
            )
            tags = [tag.strip() for tag in result.stdout.split("\n") if tag.strip()]
            return sorted([tag for tag in tags if tag.startswith("v")])
        except subprocess.CalledProcessError:
            return []

    def list_ecr_images(self, repository_name: str):
        """List ECR images with basic info"""
        if not self.ecr_client:
            return []

        try:
            response = self.ecr_client.describe_images(
                repositoryName=repository_name, maxResults=50
            )

            images = []
            for image in response.get("imageDetails", []):
                tags = image.get("imageTags", ["<untagged>"])
                pushed_at = image.get("imagePushedAt")

                # Convert datetime to string safely
                pushed_str = "unknown"
                if pushed_at:
                    if isinstance(pushed_at, datetime):
                        pushed_str = pushed_at.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        pushed_str = str(pushed_at)

                images.append(
                    {
                        "tags": tags,
                        "pushed_at": pushed_str,
                        "digest": image.get("imageDigest", "")[:12]
                        + "...",  # Truncate digest
                    }
                )

            # Sort by tags (latest first, then versions, then commits)
            def sort_key(img):
                if "latest" in img["tags"]:
                    return (0, img["pushed_at"])
                elif any(tag.startswith("v") for tag in img["tags"]):
                    return (1, img["pushed_at"])
                else:
                    return (2, img["pushed_at"])

            images.sort(key=sort_key)
            return images

        except ClientError as e:
            print(f"Error listing ECR images for {repository_name}: {e}")
            return []

    def show_status(self):
        """Show current project status"""
        print("=== Current Status ===")
        print(f"Project: {get_project_name()}")
        print(f"Version: {get_version()}")

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            )
            commit = result.stdout.strip()
            print(f"Commit:  {commit}")
        except subprocess.CalledProcessError:
            print("Commit:  unknown")
        print()

    def show_deployment_history(self):
        """Show deployment history"""
        print("=== Deployment History ===")

        # Show Git tags
        git_tags = self.list_git_tags()
        if git_tags:
            print("Recent version tags:")
            for tag in git_tags[-5:]:  # Last 5 tags
                try:
                    result = subprocess.run(
                        ["git", "log", "-1", "--format=%ci %s", tag],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    commit_info = result.stdout.strip()
                    print(f"  {tag:12} - {commit_info}")
                except subprocess.CalledProcessError:
                    print(f"  {tag:12} - (no commit info)")
        else:
            print("No version tags found")
        print()

        # Show ECR status
        print("ECR repository status:")
        for repo in self.ecr_repositories:
            print(f"{repo}:")
            images = self.list_ecr_images(repo)
            if not images:
                print("  [ERROR] No images found")
                continue

            for image in images[:3]:  # Show 3 most relevant images
                tags_str = ", ".join(image["tags"][:2])  # Show first 2 tags
                if len(image["tags"]) > 2:
                    tags_str += f" (+{len(image['tags'])-2} more)"
                print(f"  {tags_str:35} - {image['pushed_at']}")
        print()

    def deploy_by_tag(self, image_tag: str, dry_run: bool = False):
        """Deploy using a specific image tag"""
        print(f"Deploying with image tag: {image_tag}")
        if dry_run:
            print("(DRY RUN - no actual deployment)")

        # Check if tag exists in all repositories
        missing_repos = []
        for repo in self.ecr_repositories:
            images = self.list_ecr_images(repo)
            has_tag = any(image_tag in image["tags"] for image in images)
            if not has_tag:
                missing_repos.append(repo)

        if missing_repos:
            print(f"[ERROR] Tag '{image_tag}' not found in: {', '.join(missing_repos)}")
            return False

        # Run Terraform
        terraform_cmd = [
            "terraform",
            "apply" if not dry_run else "plan",
            "-auto-approve",
        ]
        terraform_cmd.extend(
            [f"-var=image_version={image_tag}", "-var-file=terraform.tfvars"]
        )

        try:
            subprocess.run(terraform_cmd, cwd="terraform/environments/prod", check=True)
            action = "planned" if dry_run else "deployed"
            print(f"[OK] Successfully {action} with tag: {image_tag}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Terraform {('plan' if dry_run else 'apply')} failed: {e}")
            return False

    def rollback_to_previous(self, dry_run: bool = False):
        """Rollback to the previous version"""
        git_tags = self.list_git_tags()
        if len(git_tags) < 2:
            print("[ERROR] Need at least 2 versions to rollback")
            return False

        previous_version = git_tags[-2]
        print(f"Rolling back to: {previous_version}")
        return self.deploy_by_tag(previous_version, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Simple deployment utilities")
    parser.add_argument("--region", default="us-east-1", help="AWS region")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("status", help="Show current status")
    subparsers.add_parser("history", help="Show deployment history")

    deploy_parser = subparsers.add_parser("deploy", help="Deploy by tag")
    deploy_parser.add_argument("tag", help="Image tag to deploy")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Plan only")

    rollback_parser = subparsers.add_parser("rollback", help="Rollback to previous")
    rollback_parser.add_argument("--dry-run", action="store_true", help="Plan only")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = DeploymentManager(aws_region=args.region)

    if args.command == "status":
        manager.show_status()
    elif args.command == "history":
        manager.show_deployment_history()
    elif args.command == "deploy":
        success = manager.deploy_by_tag(args.tag, args.dry_run)
        sys.exit(0 if success else 1)
    elif args.command == "rollback":
        success = manager.rollback_to_previous(args.dry_run)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
