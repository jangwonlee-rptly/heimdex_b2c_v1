# Multi-stage Dockerfile for Next.js web app

# Development stage
FROM node:18-alpine AS development

WORKDIR /app

# Copy package files (when they exist)
COPY package*.json ./

# Install dependencies (skip if package.json doesn't exist yet)
RUN if [ -f package.json ]; then npm install; else echo "Skipping npm install - no package.json yet"; fi

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Development command
CMD ["sh", "-c", "if [ -f package.json ]; then npm run dev; else echo 'Web app not implemented yet. Waiting...' && tail -f /dev/null; fi"]


# Production build stage
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN if [ -f package.json ]; then npm ci; fi

COPY . .

RUN if [ -f package.json ]; then npm run build; fi


# Production stage
FROM node:18-alpine AS production

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package*.json ./
RUN if [ -f package.json ]; then npm ci --only=production; fi

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["sh", "-c", "if [ -f package.json ]; then npm start; else echo 'Web app not implemented yet' && tail -f /dev/null; fi"]
