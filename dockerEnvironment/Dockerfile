FROM python:3.12.3-slim

# Install system dependencies
RUN apt-get update
RUN apt-get install -y graphviz
RUN apt-get install -y curl
RUN apt-get install -y git
RUN apt-get install -y build-essential
RUN rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install "sap-ai-sdk-gen[all]"
RUN pip install hdbcli
RUN pip install graphviz
RUN pip install pandas
RUN pip install faster-whisper

