FROM public.ecr.aws/lambda/python:3.11
ARG requirements_file
COPY $requirements_file .
RUN pip3 install -r $requirements_file --target python

