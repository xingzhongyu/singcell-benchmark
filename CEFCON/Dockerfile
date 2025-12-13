# Dockerfile for CEFCON with GPU support (CUDA 11.7)
# Base image with Ubuntu 20.04, CUDA 11.7, and cuDNN 8, which is compatible with the required PyTorch version.
FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu20.04

# Set non-interactive frontend for package installers
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
# 将pip用户安装路径添加到PATH
ENV PATH="/root/.local/bin:${PATH}"

ENV TZ=Asia/Shanghai

# Install system dependencies, Python 3.9, and R
RUN apt-get update && apt-get install -y \
    python3.9 \
    python3.9-dev \
    python3-pip \
    python3-venv \
    r-base \
    r-base-dev \
    git \
    build-essential \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Make python3.9 the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1
RUN python -m pip install --upgrade pip

# Set up the working directory
WORKDIR /app

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# --- Install Python Dependencies ---

# Install PyTorch with CUDA 11.7 support. This is a critical step.
# For CPU-only, change this line to: pip install torch==1.13.1+cpu torchvision==0.14.1+cpu torchaudio==0.13.1 --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install torch==1.13.1+cu117 torchvision==0.14.1+cu117 torchaudio==0.13.1 --extra-index-url https://download.pytorch.org/whl/cu117

# Install PyTorch Geometric dependencies matching the PyTorch and CUDA version
RUN pip install torch-scatter torch-sparse torch-cluster torch-spline-conv -f https://data.pyg.org/whl/torch-1.13.1+cu117.html

# Install the rest of the Python packages from requirements.txt
# We skip torch and torch-geometric as they were installed manually above.
RUN pip install --no-cache-dir -r requirements.txt

# --- Install R Dependencies ---
# Copy the R environment setup script
COPY r_env.R .

# Run the R script to install required packages.
# This assumes r_env.R correctly handles Bioconductor (MAST) and CRAN packages.
RUN R --no-save -q < ./r_env.R

# --- Install CEFCON ---
# Copy the entire project code into the container
COPY . .

# Install the CEFCON package itself
RUN pip install .

# Set a default command to start a bash session
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]