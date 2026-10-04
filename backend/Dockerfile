FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --locked --no-dev

COPY . .

EXPOSE 5000
CMD ["sh", "-c", "uv run python manage.py upgrade && exec uv run python server.py"]
