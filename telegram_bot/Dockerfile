FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Environment variable to ensure output is flushed directly
ENV PYTHONUNBUFFERED=1

# # Copy the entrypoint script into the container
# COPY entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

# Copy application code
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# # Set the entrypoint to the script
# ENTRYPOINT ["/entrypoint.sh"]

# Command to run your application
CMD ["python", "bot.py"]
