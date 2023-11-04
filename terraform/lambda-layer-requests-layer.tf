resource "aws_lambda_layer_version" "requests_layer" {
  layer_name               = "requests-shim"
  filename                 = "${path.module}/aws/resources/requests-layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/aws/resources/requests-layer.zip")
  compatible_runtimes      = [ "python3.11" ]
  compatible_architectures = [ "x86_64" ]
}
