FROM python:3.9-slim
WORKDIR /app
RUN pip install flask requests
COPY main.py .
EXPOSE 8000
CMD ["python", "main.py"]