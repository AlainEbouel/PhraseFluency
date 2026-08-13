FROM node:20-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS dev

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]

FROM base AS build

COPY . .
RUN npm run build

CMD ["sh", "-c", "cp -r /app/dist/. /output/"]
