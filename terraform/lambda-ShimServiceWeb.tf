resource "aws_sqs_queue" "shim_service_web_queue" {
  name                       = "ShimServiceWeb-lambda-invoker"
  visibility_timeout_seconds = 90
}

data "aws_iam_policy_document" "shim_service_web" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceWeb:*" ]
    actions   = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sns_topic.shim_error.arn ]
    actions   = [
      "sns:Publish",
      "sns:ListSubscriptionsByTopic",
      "sns:GetSubscriptionAttributes",
      "sns:Subscribe",
      "sns:Unsubscribe"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sqs_queue.shim_service_web_queue.arn ]
    actions   = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:SendMessage"
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
    actions   = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:shim-service/*" ]
    actions   = [ "secretsmanager:GetSecretValue" ]
  }

  statement {
    effect    = "Allow"
    resources = [ "${aws_lambda_function.shim_service_live_agent_poller.arn}" ]
    actions   = [ "lambda:InvokeFunction" ]
  }
}

resource "aws_iam_policy" "shim_service_web" {
  policy = data.aws_iam_policy_document.shim_service_web.json
}

resource "aws_iam_role" "shim_service_web" {
  name = "lambda-ShimServiceWeb"

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

resource "aws_iam_role_policy_attachment" "shim_service_web" {
  policy_arn = aws_iam_policy.shim_service_web.arn
  role       = aws_iam_role.shim_service_web.name
}

resource "aws_lambda_function" "shim_service_web" {
  function_name    = "ShimServiceWeb"
  description      = "Shim Service Web Lambda"
  handler          = "app.handler"
  timeout          = 90
  memory_size      = var.web_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceWeb.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceWeb.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.crypto_layer.arn,
    aws_lambda_layer_version.gcp_layer.arn,
    aws_lambda_layer_version.requests_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_web.arn

  environment {
    variables = {
      ACTIVE_PROFILES                 = "web"
      CONFIG_SERVICE_URL              = "https://sswki1xsfd.execute-api.us-west-1.amazonaws.com"
      SQS_SHIMSERVICEWEB_QUEUE_URL    = "${aws_sqs_queue.shim_service_web_queue.url}"
      SQS_PUSH_NOTIFICATION_QUEUE_URL = "${aws_sqs_queue.push_notification.url}"
      ERROR_TOPIC_ARN                 = "${aws_sns_topic.shim_error.arn}"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_web ]
}

resource "aws_cloudwatch_log_group" "shim_service_web" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_web.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_event_source_mapping" "shim_service_web" {
  event_source_arn = aws_sqs_queue.shim_service_web_queue.arn
  function_name    = "ShimServiceWeb"
  batch_size       = 1
}
