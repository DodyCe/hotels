FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home hotels && mkdir -p /data && chown hotels:hotels /data
USER hotels
CMD ["python", "gateway.py"]
