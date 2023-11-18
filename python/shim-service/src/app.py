from lambda_web_framework import app_handler


def handler(event, context):
    return app_handler.handler(event, context)
