FROM node:20-alpine
WORKDIR /app

# Install dependencies at build time for better caching.
COPY package*.json ./
RUN npm install

# Copy the rest of the app after deps are in place.
COPY . .

CMD ["npm", "start"]
