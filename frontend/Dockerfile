# --- STAGE 1: Build ---

# 使用一个包含完整构建工具的Node.js镜像
FROM node:22-alpine AS builder

# 设置工作目录
WORKDIR /app

# 1. 声明一个构建时参数
ARG REACT_APP_BACKEND_URL

# 2. 将这个构建参数设置为环境变量，以便后续的 RUN 命令可以访问
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}

# 复制 package.json 和 lock 文件
COPY package*.json ./

# 安装所有依赖
RUN npm install

# 复制所有源代码
COPY . .

# 执行生产构建
RUN npm run build

# --- STAGE 2: Production ---

# 使用nginx来提供静态文件服务
FROM nginx:alpine

# 从'builder'阶段复制构建好的build目录到nginx的html目录
COPY --from=builder /app/build /usr/share/nginx/html

# 复制nginx配置文件（如果需要自定义配置）
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露nginx运行的端口（默认为80）
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]

