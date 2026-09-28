FROM ghcr.io/astral-sh/uv:0.12-python3.13-alpine

ENV UV_COMPILE_BYTECODE=1

WORKDIR /app
COPY datacite_mock.py .
# Install the script's dependencies into the image, so starting it doesn't download anything
RUN uv sync --script datacite_mock.py

ENTRYPOINT ["uv", "run", "--script", "datacite_mock.py"]
CMD ["--host", "0.0.0.0", "--port", "8001"]
