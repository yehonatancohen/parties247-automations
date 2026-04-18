#!/bin/bash
set -e

IMAGE="yehonatancohen/parties247-auto:latest"
CONTAINER_NAME="brave_mestorf"

docker pull "$IMAGE"

NEW_IMAGE_ID=$(docker inspect --format='{{.Id}}' "$IMAGE")
CURRENT_IMAGE_ID=$(docker inspect --format='{{.Image}}' "$CONTAINER_NAME" 2>/dev/null || echo "")

if [ "$NEW_IMAGE_ID" = "$CURRENT_IMAGE_ID" ]; then
    echo "$(date): Container is already up to date."
    exit 0
fi

echo "$(date): New image detected. Restarting container..."
docker stop "$CONTAINER_NAME"
docker rm "$CONTAINER_NAME"
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    "$IMAGE"
echo "$(date): Container restarted successfully."
