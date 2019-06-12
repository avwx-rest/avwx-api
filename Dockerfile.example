# Start from the official Python 3.7 container
FROM python:3.7.3

# Expose the default Quart port
EXPOSE 8000

# Set the main working directory
WORKDIR /home/avwx

# Set the service credentials as environment variables
ENV MONGO_URI='mongodb://cache:password==@loc.test.com:12345'
ENV PSQL_URI='postgresql://localhost:5432/db'
ENV LOG_KEY='rollbar-server-key'

# Install the require Python packages
COPY requirements.txt /home/avwx/requirements.txt
RUN pip install -U pip
RUN pip install -Ur requirements.txt
RUN pip install -U hypercorn~=0.6

# Copy the application code
COPY avwx_api /home/avwx/avwx_api
COPY hypercorn_config.py /home/avwx/hypercorn_config.py

# Run the application
CMD ["hypercorn", "avwx_api:app", "-c", "python:hypercorn_config.py"]