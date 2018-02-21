"""
Gunicorn application server settings
"""

bind = '0.0.0.0:8000'

workers = 4

max_requests = 1000