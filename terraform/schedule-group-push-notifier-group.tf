resource "aws_scheduler_schedule_group" "push_notifier_group" {
  name = "ShimPushNotifierGroup"
}

data "aws_iam_policy_document" "push_notifier_group" {
  statement {
    effect    = "Allow"
    resources = [ "${aws_lambda_function.shim_notification_publisher.arn}" ]
    actions   = [
      "lambda:InvokeFunction",
      "lambda:InvokeAsync"
    ]
  }
}

resource "aws_iam_policy" "push_notifier_group" {
  policy = data.aws_iam_policy_document.push_notifier_group.json
}

resource "aws_iam_role" "push_notifier_group" {

  assume_role_policy = jsonencode({
   "Version": "2012-10-17",
   "Statement": [
    {
     "Effect": "Allow",
     "Principal": {
      "Service": "scheduler.amazonaws.com"
     },
     "Action": "sts:AssumeRole"
    }
   ]
  })
}

resource "aws_iam_role_policy_attachment" "push_notifier_group" {
  policy_arn = aws_iam_policy.push_notifier_group.arn
  role       = aws_iam_role.push_notifier_group.name
}
