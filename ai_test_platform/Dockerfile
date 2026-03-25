FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend ./backend
COPY static ./static

ENV PYTHONPATH=/app
EXPOSE 8000

# 数据目录由 docker-compose 挂载，此处仅声明
RUN mkdir -p /app/data

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
