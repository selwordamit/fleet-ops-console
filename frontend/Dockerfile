FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci

COPY . .

EXPOSE 5173

# Vite dev server; --host binds to 0.0.0.0 so it's reachable outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]