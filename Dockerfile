FROM python:3.8
ADD requirements.txt /app/
RUN pip install -U -r /app/requirements.txt
