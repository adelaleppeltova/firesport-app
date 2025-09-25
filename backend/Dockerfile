FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends gcc build-essential \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --upgrade pip && pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
