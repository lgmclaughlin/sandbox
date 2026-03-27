FROM node:20

ARG TZ
ENV TZ=$TZ

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

RUN apt-get update && apt-get install -y --no-install-recommends \
  exa \
  less \
  git \
  fzf \
  unzip \
  nano \
  vim \
  neovim \
  tmux \
  man-db \
  rclone \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG CUSTOM_CA_CERT_PATH
RUN if [ -n "$CUSTOM_CA_CERT_PATH" ] && [ -f "$CUSTOM_CA_CERT_PATH" ]; then \
  cp "$CUSTOM_CA_CERT_PATH" /usr/local/share/ca-certificates/custom-ca.crt \
  && update-ca-certificates; \
  fi

RUN mkdir -p /workspace /home/node/.local \
    && chown -R node:node /workspace /home/node/.local

WORKDIR /workspace

RUN mkdir -p /usr/local/share/npm-global/bin \
    && chown -R node:node /usr/local/share/npm-global

ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY docker/mcp-log-wrapper.py /usr/local/bin/mcp-log-wrapper
RUN chmod +x /usr/local/bin/mcp-log-wrapper

USER node

ENV SHELL=/bin/bash
ENV EDITOR=nvim
ENV VISUAL=nvim
ENV TERM=xterm-256color
ENV COLORTERM=truecolor

RUN echo "alias ls='exa -la --group-directories-first'" >> ~/.bashrc
RUN echo 'export PATH=/usr/local/share/npm-global/bin:$PATH' >> ~/.bashrc

CMD ["/usr/local/bin/entrypoint.sh"]
