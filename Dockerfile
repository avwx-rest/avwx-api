# Start from the official Python 3.11 container
FROM python:3.11.7

# Expose the default Quart port
EXPOSE 8000

# Set the main working directory
WORKDIR /home/api

# Create new user to run as non-root
RUN useradd -m -r user && chown user /home/api

# Install the required Python packages
COPY requirements.txt .
RUN pip install -U pip
RUN pip install -Ur requirements.txt --no-cache-dir --compile

# Copy the application code
COPY ./avwx_api ./avwx_api
COPY hypercorn_config.py .

# Run as new user
USER user

# Run the application
CMD ["hypercorn", "avwx_api:app", "-c", "file:hypercorn_config.py"]