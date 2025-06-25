FROM python:3.9-slim

WORKDIR /app

# Install required packages
RUN pip install flask requests

# Copy application code
COPY main.py .

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "main.py"]