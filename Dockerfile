#FROM selenium/standalone-chrome:latest

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for pyzbar and other libraries
RUN apt-get update && apt-get install -y \
    libzbar0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install -r requirements.txt

CMD ["python3", "src/bot.py"]