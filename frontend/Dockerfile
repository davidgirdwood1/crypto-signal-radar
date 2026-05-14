FROM node:22-alpine

WORKDIR /app

COPY package*.json .
RUN npm ci

COPY index.html .
COPY vite.config.js .
COPY src ./src

CMD ["npm", "run", "dev"]
