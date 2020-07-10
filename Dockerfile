FROM python:3 AS compile-image
# RUN apt-get update
# RUN apt-get install gcc gfortran python-dev libopenblas-dev liblapack-dev cython -y
ADD requirements.txt /app/
RUN pip install -U --user -r /app/requirements.txt
FROM python:slim
# RUN apt-get update
# RUN apt-get install libopenblas-dev -y
COPY --from=compile-image /root/.local/lib /root/.local/lib
COPY --from=compile-image /root/.local/bin /root/.local/bin
