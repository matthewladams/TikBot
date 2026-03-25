# build the Docker Image for arm64 and amd64
VERSION="$(python -c 'from version import get_version; print(get_version())')"

docker buildx build --push \
  --platform linux/arm64/v8,linux/amd64 \
  --build-arg TIKBOT_VERSION="${VERSION}" \
  --tag matthewladams/tikbot:latest \
  --tag matthewladams/tikbot:"${VERSION}" \
  .
