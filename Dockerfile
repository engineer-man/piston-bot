FROM python:3.10
ADD requirements.txt /app/
RUN pip install -U -r /app/requirements.txt
