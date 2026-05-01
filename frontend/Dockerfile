FROM nginx:alpine

# 把静态文件复制进容器
COPY dist/ /usr/share/nginx/html/

# 可选：替换默认 nginx 配置
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80