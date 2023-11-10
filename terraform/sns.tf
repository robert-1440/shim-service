resource "aws_sns_topic" "shim_error" {
  name         = "shim-service-error"
  display_name = "Shim Service Error"

}
