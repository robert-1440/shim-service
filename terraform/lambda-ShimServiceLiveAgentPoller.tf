resource "aws_sqs_queue" "shim_service_live_agent_poller_queue" {
  name                       = "ShimServiceLiveAgentPoller-lambda-invoker"
  visibility_timeout_seconds = 900
}

data "aws_iam_policy_document" "shim_service_live_agent_poller" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceLiveAgentPoller:*" ]
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
    resources = [ aws_sqs_queue.shim_service_live_agent_poller_queue.arn ]
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
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
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
    resources = [ "${aws_lambda_function.shim_service_notification_publisher.arn}" ]
    actions   = [ "lambda:InvokeFunction" ]
  }
}

resource "aws_iam_policy" "shim_service_live_agent_poller" {
  policy = data.aws_iam_policy_document.shim_service_live_agent_poller.json
}

resource "aws_iam_role" "shim_service_live_agent_poller" {
  name = "lambda-ShimServiceLiveAgentPoller"

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

resource "aws_iam_role_policy_attachment" "shim_service_live_agent_poller" {
  policy_arn = aws_iam_policy.shim_service_live_agent_poller.arn
  role       = aws_iam_role.shim_service_live_agent_poller.name
}

resource "aws_lambda_function" "shim_service_live_agent_poller" {
  function_name    = "ShimServiceLiveAgentPoller"
  description      = "Shim Service Live Agent Poller"
  handler          = "app.handler"
  timeout          = 900
  memory_size      = var.live_agent_poller_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceLiveAgentPoller.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceLiveAgentPoller.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.requests_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_live_agent_poller.arn

  environment {
    variables = {
      ACTIVE_PROFILES                          = "live-agent-poller"
      SQS_SHIMSERVICELIVEAGENTPOLLER_QUEUE_URL = "${aws_sqs_queue.shim_service_live_agent_poller_queue.url}"
      ERROR_TOPIC_ARN                          = "${aws_sns_topic.shim_error.arn}"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_live_agent_poller ]
}

resource "aws_cloudwatch_log_group" "shim_service_live_agent_poller" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_live_agent_poller.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_permission" "shim_service_live_agent_poller_shim_service_web" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_web.arn}"
  function_name = aws_lambda_function.shim_service_live_agent_poller.function_name
}

resource "aws_lambda_event_source_mapping" "shim_service_live_agent_poller" {
  event_source_arn = aws_sqs_queue.shim_service_live_agent_poller_queue.arn
  function_name    = "ShimServiceLiveAgentPoller"
  batch_size       = 1
}
