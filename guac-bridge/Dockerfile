FROM node:18-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --production --no-audit --no-fund

COPY server.js ./

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/health || exit 1

CMD ["node", "server.js"]
