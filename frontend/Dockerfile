FROM node:22-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app

COPY --chown=app:app package*.json ./
USER app
RUN npm install

COPY --chown=app:app . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
