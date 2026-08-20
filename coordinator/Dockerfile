FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY bgw /app/bgw
COPY coordinator /app/coordinator
CMD ["uvicorn", "coordinator.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
