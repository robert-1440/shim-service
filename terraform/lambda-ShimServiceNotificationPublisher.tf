resource "aws_iam_role" "shim_service_notification_publisher" {
  name = "lambda-ShimServiceNotificationPublisher"

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

data "aws_iam_policy_document" "shim_service_notification_publisher" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceNotificationPublisher:*" ]
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

  statement {
    effect    = "Allow"
    resources = [ "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceLambdaScheduler" ]
    actions   = [
      "lambda:InvokeFunction",
      "lambda:GetFunction"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ "*" ]
    actions   = [
      "scheduler:CreateSchedule",
      "scheduler:DeleteSchedule"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ "${aws_iam_role.push_notifier_group.arn}" ]
    actions   = [ "iam:PassRole" ]
  }
}

resource "aws_iam_policy" "shim_service_notification_publisher" {
  policy = data.aws_iam_policy_document.shim_service_notification_publisher.json
}

resource "aws_iam_role_policy_attachment" "shim_service_notification_publisher" {
  policy_arn = aws_iam_policy.shim_service_notification_publisher.arn
  role       = aws_iam_role.shim_service_notification_publisher.name
}

resource "aws_lambda_function" "shim_service_notification_publisher" {
  function_name    = "ShimServiceNotificationPublisher"
  description      = "Shim Service Notification Publisher"
  handler          = "app.handler"
  timeout          = 60
  memory_size      = var.notification_publisher_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceNotificationPublisher.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceNotificationPublisher.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.gcp_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_notification_publisher.arn

  environment {
    variables = {
      ACTIVE_PROFILES                 = "notification-publisher"
      PUSH_NOTIFIER_GROUP             = "ShimPushNotifierGroup"
      PUSH_NOTIFIER_GROUP_ROLE_ARN    = "${aws_iam_role.push_notifier_group.arn}"
      SQS_PUSH_NOTIFICATION_QUEUE_URL = "${aws_sqs_queue.push_notification.url}"
      ERROR_TOPIC_ARN                 = "${aws_sns_topic.shim_error.arn}"
      THIS_FUNCTION_ARN               = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceNotificationPublisher"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_notification_publisher ]
}

resource "aws_cloudwatch_log_group" "shim_service_notification_publisher" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_notification_publisher.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_permission" "shim_service_notification_publisher_shim_service_lambda_scheduler" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_lambda_scheduler.arn}"
  function_name = aws_lambda_function.shim_service_notification_publisher.function_name
}

resource "aws_lambda_permission" "shim_service_notification_publisher_shim_service_pub_sub_poller" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_pub_sub_poller.arn}"
  function_name = aws_lambda_function.shim_service_notification_publisher.function_name
}

resource "aws_lambda_permission" "shim_service_notification_publisher_shim_service_live_agent_poller" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_live_agent_poller.arn}"
  function_name = aws_lambda_function.shim_service_notification_publisher.function_name
}
