## ------------------------------- Builder Stage ------------------------------ ## 
FROM python:3.11-bookworm AS builder

RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Download the latest installer, install it and then remove it
ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod -R 655 /install.sh && /install.sh && rm /install.sh

# Set up the UV environment path correctly
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY ./pyproject.toml .

RUN uv sync

## ------------------------------- Production Stage ------------------------------ ##
FROM python:3.11-slim-bookworm AS production

# 환경 변수 설정: 바이트코드 생성 방지, stdout/stderr 버퍼링 해제
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create the working directory
WORKDIR /app

# Copy the application code from the builder stage
COPY . .

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv .venv

# Set up environment variables for production
ENV PATH="/app/.venv/bin:$PATH"

# Expose the specified port for FastAPI
EXPOSE $PORT

# Execute the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0" , "--port", "8080"]