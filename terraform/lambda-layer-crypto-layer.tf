resource "aws_lambda_layer_version" "crypto_layer" {
  layer_name               = "crypto-shim"
  filename                 = "${path.module}/aws/resources/crypto-layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/aws/resources/crypto-layer.zip")
  compatible_runtimes      = [ "python3.11" ]
  compatible_architectures = [ "x86_64" ]
}
