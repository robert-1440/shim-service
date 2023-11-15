resource "aws_iam_role" "shim_service_live_agent_poller_mirror" {
  name = "lambda-ShimServiceLiveAgentPollerMirror"

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

data "aws_iam_policy_document" "shim_service_live_agent_poller_mirror" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceLiveAgentPollerMirror:*" ]
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
    resources = [ "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceNotificationPublisher" ]
    actions   = [
      "lambda:InvokeFunction",
      "lambda:GetFunction"
    ]
  }
}

resource "aws_iam_policy" "shim_service_live_agent_poller_mirror" {
  policy = data.aws_iam_policy_document.shim_service_live_agent_poller_mirror.json
}

resource "aws_iam_role_policy_attachment" "shim_service_live_agent_poller_mirror" {
  policy_arn = aws_iam_policy.shim_service_live_agent_poller_mirror.arn
  role       = aws_iam_role.shim_service_live_agent_poller_mirror.name
}

resource "aws_lambda_function" "shim_service_live_agent_poller_mirror" {
  function_name    = "ShimServiceLiveAgentPollerMirror"
  description      = "Shim Service Live Agent Poller"
  handler          = "app.handler"
  timeout          = 60
  memory_size      = var.live_agent_poller_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceLiveAgentPollerMirror.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceLiveAgentPollerMirror.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.requests_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_live_agent_poller_mirror.arn

  environment {
    variables = {
      ACTIVE_PROFILES      = "live-agent-poller"
      ERROR_TOPIC_ARN      = "${aws_sns_topic.shim_error.arn}"
      MIRROR_FUNCTION_NAME = "ShimServiceLiveAgentPoller"
      THIS_FUNCTION_ARN    = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceLiveAgentPollerMirror"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_live_agent_poller_mirror ]
}

resource "aws_cloudwatch_log_group" "shim_service_live_agent_poller_mirror" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_live_agent_poller_mirror.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_permission" "shim_service_live_agent_poller_mirror_shim_service_lambda_scheduler" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_lambda_scheduler.arn}"
  function_name = aws_lambda_function.shim_service_live_agent_poller_mirror.function_name
}
