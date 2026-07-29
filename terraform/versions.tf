terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # No remote backend configured yet — state stays local (terraform.tfstate,
  # gitignored). For a real multi-person team, replace this with an S3 +
  # DynamoDB backend before anyone else touches this infra.
}

provider "aws" {
  region = var.aws_region
}
