# Usamos la versión de Python 3.12 especificada en el manual
FROM python:3.12-slim-bookworm

# Evitar interrupciones interactivas durante la instalación de paquetes
ENV DEBIAN_FRONTEND=noninteractive

# 1. Instalar herramientas de compilación (build-essential) y dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    python3-dev \
    libcairo2-dev \
    fonts-dejavu-core \
    imagemagick \
    libvips-tools \
    && rm -rf /var/lib/apt/lists/*

# 2. Descargar e instalar Node.js v20.x tal y como pide el manual
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 3. Instalar la herramienta global invenio-cli
RUN pip install --no-cache-dir invenio-cli

# Definir el directorio de trabajo dentro del contenedor
WORKDIR /app

# Exponer el puerto por el que responde la app
EXPOSE 5000

# Comando por defecto para iniciar el servidor de desarrollo de Invenio
CMD ["invenio-cli", "run"]
