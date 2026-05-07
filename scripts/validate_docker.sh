#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${DOCKER_IMAGE_TAG:-syncorswim-backend:ci}"
CONTAINER_NAME="${DOCKER_CONTAINER_NAME:-syncorswim-backend-ci}"
HOST_PORT="${DOCKER_HOST_PORT:-}"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

show_logs() {
  echo "Docker container logs:"
  echo "----------------------------------------"
  docker logs "$CONTAINER_NAME" 2>&1 || true
  echo "----------------------------------------"
}

trap cleanup EXIT

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not available. Start Docker and retry."
  exit 1
fi

echo "Building Docker image ${IMAGE_TAG}..."
docker build -t "$IMAGE_TAG" backend

cleanup

echo "Starting Docker container ${CONTAINER_NAME}..."
if [ -n "$HOST_PORT" ]; then
  PORT_SPEC="127.0.0.1:${HOST_PORT}:8000"
else
  PORT_SPEC="127.0.0.1::8000"
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  -e DATABASE_URL=sqlite+pysqlite:////tmp/syncorswim.db \
  -e PUSH_TOKEN=test-token \
  -p "$PORT_SPEC" \
  "$IMAGE_TAG" >/dev/null

MAPPED_PORT=$(docker port "$CONTAINER_NAME" 8000/tcp | awk -F: 'NR == 1 { print $NF }')
HEALTH_URL="http://127.0.0.1:${MAPPED_PORT}/api/health"

echo "Waiting for ${HEALTH_URL}..."
for _ in $(seq 1 30); do
  if curl --fail --silent "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Docker smoke test passed."
    exit 0
  fi

  if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || echo false)" != "true" ]; then
    echo "Docker container exited before becoming healthy."
    show_logs
    exit 1
  fi

  sleep 1
done

echo "Docker container did not become healthy in time."
show_logs
exit 1
