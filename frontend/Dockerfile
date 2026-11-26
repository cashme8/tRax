# Development image for the Next.js app.
FROM node:24-alpine

WORKDIR /app

# Install dependencies first so Docker caches this layer until package files change.
COPY package.json package-lock.json ./
RUN npm ci

# In dev, compose mounts ./frontend over /app so edits hot-reload.
COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
