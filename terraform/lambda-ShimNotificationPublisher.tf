data "aws_iam_policy_document" "shim_notification_publisher" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimNotificationPublisher:*" ]
    actions   = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sns_topic.shim_error.arn ]
    actions   = [ "sns:Publish" ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sns_topic.shim_mock_push_notification.arn ]
    actions   = [ "sns:Publish" ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_session.arn ]
    actions   = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_virtual_range_table.arn ]
    actions   = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_virtual_table.arn ]
    actions   = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_event.arn ]
    actions   = [ "dynamodb:PutItem" ]
  }

  statement {
    effect    = "Allow"
    resources = [ "*" ]
    actions   = [
      "scheduler:CreateSchedule",
      "scheduler:DeleteSchedule"
    ]
  }
}

resource "aws_iam_policy" "shim_notification_publisher" {
  policy = data.aws_iam_policy_document.shim_notification_publisher.json
}

resource "aws_iam_role" "shim_notification_publisher" {
  name = "lambda-ShimNotificationPublisher"

  assume_role_policy = jsonencode({
   "Version": "2012-10-17",
   "Statement": [
    {
     "Effect": "Allow",
     "Principal": {
      "Service": "lambda.amazonaws.com"
     },
     "Action": "sts:AssumeRole"
    }
   ]
  })
}

resource "aws_iam_role_policy_attachment" "shim_notification_publisher" {
  policy_arn = aws_iam_policy.shim_notification_publisher.arn
  role       = aws_iam_role.shim_notification_publisher.name
}

resource "aws_lambda_function" "shim_notification_publisher" {
  function_name    = "ShimNotificationPublisher"
  description      = "Shim Service Notification Publisher"
  handler          = "app.handler"
  timeout          = 900
  memory_size      = var.notification_publisher_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimNotificationPublisher.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimNotificationPublisher.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.gcp_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_notification_publisher.arn

  environment {
    variables = {
      SHIM_SERVICE_PUSH_NOTIFIER          = "ShimPushNotifierGroup"
      SHIM_SERVICE_PUSH_NOTIFIER_ROLE_ARN = "${aws_iam_role.push_notifier_group.arn}"
      ERROR_TOPIC_ARN                     = "${aws_sns_topic.shim_error.arn}"
      SNS_PUSH_TOPIC_ARN                  = "${aws_sns_topic.shim_mock_push_notification.arn}"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_notification_publisher ]
}

resource "aws_cloudwatch_log_group" "shim_notification_publisher" {
  name              = "/aws/lambda/${aws_lambda_function.shim_notification_publisher.function_name}"
  retention_in_days = 30
}
