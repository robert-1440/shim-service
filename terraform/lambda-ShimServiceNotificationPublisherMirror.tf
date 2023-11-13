resource "aws_sqs_queue" "shim_service_notification_publisher_mirror_queue" {
  name                       = "ShimServiceNotificationPublisherMirror-lambda-invoker"
  visibility_timeout_seconds = 900
  delay_seconds              = 10
}

data "aws_iam_policy_document" "shim_service_notification_publisher_mirror" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceNotificationPublisherMirror:*" ]
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
    resources = [ aws_sqs_queue.push_notification.arn ]
    actions   = [
      "sqs:SendMessage",
      "sqs:GetQueueUrl"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sqs_queue.shim_service_notification_publisher_queue.arn ]
    actions   = [ "sqs:SendMessage" ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sqs_queue.shim_service_notification_publisher_mirror_queue.arn ]
    actions   = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_session.arn ]
    actions   = [
      "dynamodb:BatchGetItem",
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
      "dynamodb:DeleteItem",
      "dynamodb:Query"
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
}

resource "aws_iam_policy" "shim_service_notification_publisher_mirror" {
  policy = data.aws_iam_policy_document.shim_service_notification_publisher_mirror.json
}

resource "aws_iam_role" "shim_service_notification_publisher_mirror" {
  name = "lambda-ShimServiceNotificationPublisherMirror"

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

resource "aws_iam_role_policy_attachment" "shim_service_notification_publisher_mirror" {
  policy_arn = aws_iam_policy.shim_service_notification_publisher_mirror.arn
  role       = aws_iam_role.shim_service_notification_publisher_mirror.name
}

resource "aws_lambda_function" "shim_service_notification_publisher_mirror" {
  function_name    = "ShimServiceNotificationPublisherMirror"
  description      = "Shim Service Notification Publisher"
  handler          = "app.handler"
  timeout          = 900
  memory_size      = var.notification_publisher_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceNotificationPublisherMirror.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceNotificationPublisherMirror.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.gcp_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_notification_publisher_mirror.arn

  environment {
    variables = {
      ACTIVE_PROFILES                                = "notification-publisher"
      SQS_SHIMSERVICENOTIFICATIONPUBLISHER_QUEUE_URL = "${aws_sqs_queue.shim_service_notification_publisher_queue.url}"
      SQS_PUSH_NOTIFICATION_QUEUE_URL                = "${aws_sqs_queue.push_notification.url}"
      ERROR_TOPIC_ARN                                = "${aws_sns_topic.shim_error.arn}"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_notification_publisher_mirror ]
}

resource "aws_cloudwatch_log_group" "shim_service_notification_publisher_mirror" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_notification_publisher_mirror.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_event_source_mapping" "shim_service_notification_publisher_mirror" {
  event_source_arn = aws_sqs_queue.shim_service_notification_publisher_mirror_queue.arn
  function_name    = "ShimServiceNotificationPublisherMirror"
  batch_size       = 1
  depends_on = [ aws_lambda_function.shim_service_notification_publisher_mirror ]
}