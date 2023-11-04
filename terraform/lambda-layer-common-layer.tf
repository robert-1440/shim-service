resource "aws_lambda_layer_version" "common_layer" {
  layer_name               = "common-shim"
  filename                 = "${path.module}/aws/resources/common-layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/aws/resources/common-layer.zip")
  compatible_runtimes      = [ "python3.11" ]
  compatible_architectures = [ "x86_64" ]
}
