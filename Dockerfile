FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home hotels && mkdir -p /data && chown hotels:hotels /data
USER hotels
CMD ["python", "gateway.py"]
