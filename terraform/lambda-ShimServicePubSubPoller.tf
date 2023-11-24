resource "aws_iam_role" "shim_service_pub_sub_poller" {
  name = "lambda-ShimServicePubSubPoller"

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

data "aws_iam_policy_document" "shim_service_pub_sub_poller" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServicePubSubPoller:*" ]
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
    resources = [ aws_dynamodb_table.shim_service_session.arn ]
    actions   = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query"
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
    resources = [ "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceNotificationPublisher" ]
    actions   = [
      "lambda:InvokeFunction",
      "lambda:GetFunction"
    ]
  }
}

resource "aws_iam_policy" "shim_service_pub_sub_poller" {
  policy = data.aws_iam_policy_document.shim_service_pub_sub_poller.json
}

resource "aws_iam_role_policy_attachment" "shim_service_pub_sub_poller" {
  policy_arn = aws_iam_policy.shim_service_pub_sub_poller.arn
  role       = aws_iam_role.shim_service_pub_sub_poller.name
}

resource "aws_lambda_function" "shim_service_pub_sub_poller" {
  function_name    = "ShimServicePubSubPoller"
  description      = "Shim Service PubSub Poller"
  handler          = "app.handler"
  timeout          = 60
  memory_size      = var.pubsub_poller_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServicePubSubPoller.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServicePubSubPoller.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.platform_events_layer.arn,
    aws_lambda_layer_version.requests_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_pub_sub_poller.arn

  environment {
    variables = {
      ACTIVE_PROFILES   = "pubsub-poller"
      PUBSUB_TOPIC      = "/event/RS_L__ConversationMessage__e"
      ERROR_TOPIC_ARN   = "${aws_sns_topic.shim_error.arn}"
      THIS_FUNCTION_ARN = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServicePubSubPoller"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_pub_sub_poller ]
}

resource "aws_cloudwatch_log_group" "shim_service_pub_sub_poller" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_pub_sub_poller.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_permission" "shim_service_pub_sub_poller_shim_service_lambda_scheduler" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_lambda_scheduler.arn}"
  function_name = aws_lambda_function.shim_service_pub_sub_poller.function_name
}
