FROM nginx:alpine

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 拷贝自定义配置
COPY nginx.conf /etc/nginx/nginx.conf

# 拷贝前端静态资源
COPY dist/ /usr/share/nginx/html/

# 暴露端口
EXPOSE 8001

CMD ["nginx", "-g", "daemon off;"]