resource "aws_sns_topic" "shim_mock_push_notification" {
  name         = "shim-service-mock-push-notification"
  display_name = "Shim Service Mock Push Notification"

}

resource "aws_sns_topic" "shim_error" {
  name         = "shim-service-error"
  display_name = "Shim Service Error"

}
