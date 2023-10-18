# Use an official Python image
FROM python:3.9

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

# Copy only necessary Python scripts
COPY calculator.py .
COPY compressionMessages.py .
COPY dbInteraction.py .
COPY downloader.py .
COPY main.py .
COPY validator.py .

# Set the default command to run your app, assuming main.py is the entry point
CMD ["python", "main.py"]
