data "template_file" "shim_service_requests_api" {
  template = file("aws/resources/shim-service-requests.tpl.json")
  vars     = {
    uri = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.shim_service_web.arn}/invocations"
  }
}

resource "aws_api_gateway_rest_api" "shim_service_requests" {
  name        = "shim-service-requests${var.rest_api_suffix}"
  description = "Shim Service"
  body        = data.template_file.shim_service_requests_api.rendered
}

resource "aws_api_gateway_deployment" "shim_service_requests_api" {
  rest_api_id = aws_api_gateway_rest_api.shim_service_requests.id

  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.shim_service_requests.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "shim_service_requests_api" {
  deployment_id = aws_api_gateway_deployment.shim_service_requests_api.id
  rest_api_id   = aws_api_gateway_rest_api.shim_service_requests.id
  stage_name    = "shim-service"
}
