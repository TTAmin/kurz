terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.68"
    }
  }

  # Local state keeps the demo self-contained. In a team, use a remote backend:
  # backend "s3" {
  #   bucket       = "my-tf-state"
  #   key          = "kurz/terraform.tfstate"
  #   region       = "eu-central-1"
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "kurz"
      ManagedBy = "terraform"
    }
  }
}
