FROM python:3.13-slim
WORKDIR /app
COPY services/booking/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/booking /app/services/booking
COPY services/__init__.py /app/services/__init__.py
ENV PYTHONPATH=/app
EXPOSE 8003
CMD ["uvicorn", "services.booking.main:app", "--host", "0.0.0.0", "--port", "8003"]
