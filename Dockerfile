FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# El scheduler mantiene el contenedor vivo y ejecuta main.py a diario
CMD ["python", "scheduler.py"]
