terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Endpoints, credentials, and validation skips are injected by `tflocal`
# at apply time. This block stays clean so it would target real AWS by
# running plain `terraform` instead of `tflocal`.
provider "aws" {
  region = "us-east-1"
}
