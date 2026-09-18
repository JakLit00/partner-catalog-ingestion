FROM node:22.23.2-bookworm-slim

RUN npm install --global json-server@0.17.4

WORKDIR /app

COPY db.json ./db.json
COPY DUMMYJSON-LICENSE.txt ./DUMMYJSON-LICENSE.txt

USER node

EXPOSE 3000

CMD ["json-server", "db.json", "--host", "0.0.0.0", "--port", "3000", "--read-only"]