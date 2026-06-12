FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 

WORKDIR /sim

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./simulator

CMD ["python", "-m", "simulator.app.main"]
