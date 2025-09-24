# Use an official Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy only necessary Python scripts
COPY calculator.py .
COPY compressionMessages.py .
COPY dbInteraction.py .
COPY downloader.py .
COPY main.py .
COPY validator.py .

# Set the default command to run your app, assuming main.py is the entry point
CMD ["python", "main.py"]
