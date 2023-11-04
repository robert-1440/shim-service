resource "aws_lambda_layer_version" "gcp_layer" {
  layer_name               = "gcp-shim"
  filename                 = "${path.module}/aws/resources/gcp-layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/aws/resources/gcp-layer.zip")
  compatible_runtimes      = [ "python3.11" ]
  compatible_architectures = [ "x86_64" ]
}
