FROM node:latest
WORKDIR /app
COPY . .
RUN npm install
ENV SESSION_SECRET=EXAMPLE-not-a-real-secret
EXPOSE 3000
CMD ["node", "app.js"]
