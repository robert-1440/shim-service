resource "aws_iam_role" "shim_service_lambda_scheduler" {
  name = "lambda-ShimServiceLambdaScheduler"

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

data "aws_iam_policy_document" "shim_service_lambda_scheduler" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceLambdaScheduler:*" ]
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
    resources = [ "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceLiveAgentPoller" ]
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

  statement {
    effect    = "Allow"
    resources = [ "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServicePubSubPoller" ]
    actions   = [
      "lambda:InvokeFunction",
      "lambda:GetFunction"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ShimServiceWeb" ]
    actions   = [
      "lambda:InvokeFunction",
      "lambda:GetFunction"
    ]
  }
}

resource "aws_iam_policy" "shim_service_lambda_scheduler" {
  policy = data.aws_iam_policy_document.shim_service_lambda_scheduler.json
}

resource "aws_iam_role_policy_attachment" "shim_service_lambda_scheduler" {
  policy_arn = aws_iam_policy.shim_service_lambda_scheduler.arn
  role       = aws_iam_role.shim_service_lambda_scheduler.name
}

resource "aws_lambda_function" "shim_service_lambda_scheduler" {
  function_name    = "ShimServiceLambdaScheduler"
  description      = "Shim Service Lambda Scheduler"
  handler          = "app.handler"
  timeout          = 90
  memory_size      = var.scheduler_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceLambdaScheduler.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceLambdaScheduler.zip")
  layers           = [
    aws_lambda_layer_version.common_layer.arn,
    aws_lambda_layer_version.requests_layer.arn
  ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_lambda_scheduler.arn

  environment {
    variables = {
      ACTIVE_PROFILES = "scheduler"
      ERROR_TOPIC_ARN = "${aws_sns_topic.shim_error.arn}"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_lambda_scheduler ]
}

resource "aws_cloudwatch_log_group" "shim_service_lambda_scheduler" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_lambda_scheduler.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_permission" "shim_service_lambda_scheduler_shim_service_pub_sub_poller" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_pub_sub_poller.arn}"
  function_name = aws_lambda_function.shim_service_lambda_scheduler.function_name
}

resource "aws_lambda_permission" "shim_service_lambda_scheduler_shim_service_notification_publisher" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_notification_publisher.arn}"
  function_name = aws_lambda_function.shim_service_lambda_scheduler.function_name
}

resource "aws_lambda_permission" "shim_service_lambda_scheduler_shim_service_live_agent_poller" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_live_agent_poller.arn}"
  function_name = aws_lambda_function.shim_service_lambda_scheduler.function_name
}

resource "aws_lambda_permission" "shim_service_lambda_scheduler_shim_service_table_listener" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_table_listener.arn}"
  function_name = aws_lambda_function.shim_service_lambda_scheduler.function_name
}

resource "aws_lambda_permission" "shim_service_lambda_scheduler_shim_service_web" {
  principal     = "lambda.amazonaws.com"
  action        = "lambda:InvokeFunction"
  source_arn    = "${aws_lambda_function.shim_service_web.arn}"
  function_name = aws_lambda_function.shim_service_lambda_scheduler.function_name
}
