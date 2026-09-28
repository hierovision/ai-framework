FROM node:20
WORKDIR /app
COPY release/checkout-service-3.4.1.tar.gz .
RUN tar xzf checkout-service-3.4.1.tar.gz
CMD ["node", "server.js"]
