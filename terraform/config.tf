terraform {
  backend "s3" {
    bucket               = "infra-terraform-1440"
    key                  = "shim-service/terraform.tfstate"
    region               = "us-west-1"
    workspace_key_prefix = "envs"
  }

}
