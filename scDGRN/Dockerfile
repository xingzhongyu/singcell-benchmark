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

# 升级pip
RUN python -m pip install --no-cache-dir --upgrade pip wheel

# ------------------------------------------------------------------
# Python Dependencies Installation
# ------------------------------------------------------------------
# 设置工作目录
WORKDIR /app

# 仅复制requirements.txt文件，以利用Docker的层缓存
# 只有当requirements.txt文件改变时，才会重新运行下面的pip install指令
COPY requirements.txt .

# 安装Python依赖
# --no-cache-dir 减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt

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
CMD ["/bin/bash"]