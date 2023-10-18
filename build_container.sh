# build the Docker Image for arm64 and amd64
docker buildx build --push \
  --platform linux/arm64/v8,linux/amd64 \
  --tag matthewladams/tikbot:latest \
  .