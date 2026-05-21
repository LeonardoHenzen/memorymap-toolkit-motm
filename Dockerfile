FROM python:3.9-bullseye

# Install Python and build tools 
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    gcc \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && apt-get clean
    
# Upgrade pip & setuptools
RUN python3 -m pip install --upgrade pip "setuptools<60" wheel

# Install app requirements
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install -r /tmp/requirements.txt

# App setup
WORKDIR /app
COPY . /app

# Non-root user
RUN useradd -u 5678 -ms /bin/bash appuser && chown -R appuser /app
USER appuser

# Create folders
RUN mkdir -p static media logs backups

# Copy secret settings
# this is better done via compose volume
# RUN cp memorymap_toolkit/settings/secret_settings_template.py memorymap_toolkit/settings/secret_settings.py

# Start command
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]