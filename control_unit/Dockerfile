FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE ${CU_PORT}

ENV DOCKER_CONTAINER=True

CMD ["python", "web_service.py"]
