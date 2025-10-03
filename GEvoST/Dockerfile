# ------------------------------------------------------------------
# Stage 1: Base Image with CUDA and System Dependencies
# ------------------------------------------------------------------
# 使用NVIDIA官方的CUDA 12.4.1镜像，它基于Ubuntu 22.04。
# -devel 镜像包含完整的编译工具链，对于安装FAISS等需要编译的库很有用。
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

# 设置环境变量，避免apt-get安装时出现交互式提示
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# ------------------------------------------------------------------
# Install System Dependencies
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3-venv \
    git \
    wget \
    build-essential \
    cmake \
    # rpy2 需要 R 语言环境
    r-base \
    # faiss 和其他科学计算库可能需要的依赖
    libopenblas-dev \
    liblapack-dev \
    # 清理apt缓存以减小镜像大小
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 将python3.10设置为默认的python和pip
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# ------------------------------------------------------------------
# Install Python Packages
# ------------------------------------------------------------------
WORKDIR /app

# 升级pip
RUN python -m pip install --upgrade pip

# --- 关键步骤：分阶段安装Python依赖 ---

# 1. 安装PyTorch, Torchvision, Torchaudio, Triton
#    使用官方的index-url确保下载到正确的CUDA 12.4版本
#    我们根据torchvision和torchaudio的版本推断torch版本为2.4.0
RUN pip install \
    torch==2.4.0 \
    torchvision==0.19.0 \
    torchaudio==2.4.0 \
    triton==3.0.0 \
    --index-url https://download.pytorch.org/whl/cu124

# 2. 安装PyG (PyTorch Geometric) 和 DGL 相关包
#    这些包同样需要从特定的wheel仓库下载，以匹配PyTorch和CUDA版本
RUN pip install \
    dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html && \
    pip install \
    torch_scatter==2.1.2+pt24cu124 \
    torch_sparse==0.6.18+pt24cu124 \
    torch_cluster==1.6.3+pt24cu124 \
    torch_spline_conv==1.2.2+pt24cu124 \
    pyg-lib==0.4.0+pt24cu124 \
    torch-geometric==2.6.1 \
    -f https://data.pyg.org/whl/torch-2.4.0+cu124.html

# 3. 安装剩余的通用包
#    首先复制requirements.txt，利用Docker的层缓存机制
COPY requirements.txt .
#    安装其他所有依赖
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------
# Copy Application Code and Set Entrypoint
# ------------------------------------------------------------------
# 将你的算法代码复制到容器中
COPY . .

# 设置默认命令为bash，方便进入容器后进行调试
CMD ["bash"]