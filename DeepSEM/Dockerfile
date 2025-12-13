# ------------------------------------------------------------------
# Stage 1: Base Image
# ------------------------------------------------------------------
# 使用NVIDIA官方CUDA 11.4镜像，包含cuDNN 8和开发工具，基于Ubuntu 20.04
FROM nvidia/cuda:11.4.3-cudnn8-devel-ubuntu20.04

# ------------------------------------------------------------------
# Metadata and Environment Variables
# ------------------------------------------------------------------


# 设置环境变量，防止安装过程中出现交互式提示
ENV DEBIAN_FRONTEND=noninteractive
# 确保Python输出能立即打印到终端，方便调试
ENV PYTHONUNBUFFERED=1
# 将pip用户安装路径添加到PATH
ENV PATH="/root/.local/bin:${PATH}"

ENV TZ=Asia/Shanghai

# ------------------------------------------------------------------
# System Dependencies
# ------------------------------------------------------------------
# 安装Python 3.8, pip, git以及graphviz等系统依赖
# graphviz Python包需要系统级的graphviz库
RUN apt-get update && apt-get install -y \
    python3.8 \
    python3.8-dev \
    python3-pip \
    git \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# 将python3.8设置为默认的python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1

# 升级pip并配置镜像源
RUN python -m pip install --no-cache-dir --upgrade pip wheel setuptools

# 配置pip使用清华镜像源加速下载（国内访问更快）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# ------------------------------------------------------------------
# Python Dependencies Installation
# ------------------------------------------------------------------
# 设置工作目录
WORKDIR /app

# 仅复制requirements.txt文件，以利用Docker的层缓存
# 只有当requirements.txt文件改变时，才会重新运行下面的pip install指令
COPY requirements.txt .

# 分步安装依赖以优化构建速度和错误处理
# 1. 先安装PyTorch及其相关包（使用CUDA 11.4对应的版本）
#    CUDA 11.4可以使用cu116或cu117的PyTorch版本
#    优先尝试从PyTorch官方源安装CUDA版本，如果失败则使用镜像源
RUN pip install --no-cache-dir \
    torch==1.13.1+cu117 \
    torchvision==0.14.1+cu117 \
    torchaudio==0.13.1 \
    --extra-index-url https://download.pytorch.org/whl/cu117 || \
    (echo "CUDA version failed, trying CPU version from mirror" && \
     pip install --no-cache-dir \
     torch==1.13.1 \
     torchvision==0.14.1 \
     torchaudio==0.13.1)

# 2. 安装基础科学计算库（这些是其他包的依赖，需要先安装）
RUN pip install --no-cache-dir \
    numpy==1.23.4 \
    Cython==0.29.33 \
    joblib==1.2.0 \
    scipy \
    threadpoolctl==3.1.0

# 3. 安装剩余依赖
#    从requirements.txt中排除已安装的PyTorch相关包，避免重复安装
#    使用grep排除以torch开头的行（包括torch、torchaudio、torchvision）
RUN grep -vE "^(torch|torchaudio|torchvision)" requirements.txt > /tmp/requirements_filtered.txt && \
    pip install --no-cache-dir -r /tmp/requirements_filtered.txt && \
    rm /tmp/requirements_filtered.txt

# ------------------------------------------------------------------
# Application Code and Final Configuration
# ------------------------------------------------------------------
# 复制项目代码到工作目录
# 建议使用 .dockerignore 文件排除不需要的文件（如.git, venv, __pycache__）
COPY . .

# 暴露端口（如果你的应用是网络服务，例如Flask/Django/Streamlit）
# EXPOSE 8501

# 容器启动时默认执行的命令
# 这里设置为bash，方便您进入容器后进行调试或手动运行脚本
# 您可以根据需要修改为 `CMD ["python", "your_main_script.py"]`
# Set a default command to start a bash session
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]