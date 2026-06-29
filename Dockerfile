FROM python:3.11-slim

RUN mkdir -p /data /output /scripts
COPY convert_fairfield.py /scripts/convert_fairfield.py

WORKDIR /data
CMD ["python", "/scripts/convert_fairfield.py", "/data/*.SEGD", "-o", "/output/"]
