FROM node:20-alpine

RUN apk add --no-cache \
    python3 \
    py3-pip \
    git \
    bash \
    curl \
    jq

RUN npm install -g opencode-ai

RUN opencode auth login --token placeholder 2>/dev/null || true

RUN mkdir -p /codeaudit
WORKDIR /github/workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
