FROM python:3.13-slim
WORKDIR /app
COPY services/user/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/user /app/services/user
COPY services/__init__.py /app/services/__init__.py
ENV PYTHONPATH=/app
EXPOSE 8001
CMD ["uvicorn", "services.user.main:app", "--host", "0.0.0.0", "--port", "8001"]
