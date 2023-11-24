resource "aws_lambda_layer_version" "platform_events_layer" {
  layer_name               = "platform-events-shim"
  filename                 = "${path.module}/aws/resources/platform-events-layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/aws/resources/platform-events-layer.zip")
  compatible_runtimes      = [ "python3.11" ]
  compatible_architectures = [ "x86_64" ]
}
