provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      shim-1440 = 1
    }
  }
}

data "aws_caller_identity" "current" {
}
