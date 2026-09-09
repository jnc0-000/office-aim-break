FROM debian:bookworm-slim AS builder

ARG CPUMINER_REPO=https://github.com/pooler/cpuminer.git
ARG CPUMINER_REF=5f02105940edb61144c09a7eb960bba04a10d5b7

RUN apt-get -o Acquire::Retries=10 -o Acquire::http::Pipeline-Depth=0 update \
    && apt-get -o Acquire::Retries=10 -o Acquire::http::Pipeline-Depth=0 install -y --fix-missing --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
        automake \
        autoconf \
        libcurl4-openssl-dev \
        libssl-dev \
        libjansson-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone "${CPUMINER_REPO}" cpuminer \
    && cd cpuminer \
    && git checkout "${CPUMINER_REF}" \
    && ./autogen.sh \
    && ./configure CFLAGS="-O3" \
    && make -j"$(nproc)"

FROM debian:bookworm-slim

RUN apt-get -o Acquire::Retries=10 -o Acquire::http::Pipeline-Depth=0 update \
    && apt-get -o Acquire::Retries=10 -o Acquire::http::Pipeline-Depth=0 install -y --fix-missing --no-install-recommends \
        ca-certificates \
        libcurl4 \
        libjansson4 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/cpuminer/minerd /usr/local/bin/minerd
COPY start-btc-miner.sh /usr/local/bin/start-btc-miner.sh

RUN chmod +x /usr/local/bin/start-btc-miner.sh

ENV BTC_ALGO=sha256d
ENV BTC_THREADS=1

CMD ["/usr/local/bin/start-btc-miner.sh"]
