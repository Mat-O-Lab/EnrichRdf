# EnrichRdf
[![Publish Docker image](https://github.com/Mat-O-Lab/EnrichRdf/actions/workflows/PublishContainer.yml/badge.svg)](https://github.com/Mat-O-Lab/EnrichRdf/actions/workflows/PublishContainer.yml)

Base App for FastApi with one page Starlette Form as index page, converts rdf graphs to multiple formats as example.

# how to use

## create a .env file with
```bash
APP_PORT=<your-port>
APP_MODE=<"development" or "production">
ADMIN_NAME=<name_of_admin>
ADMIN_MAIL=<email_of_admin>
ORG_SITE=<org_website>
```

## docker-compose
Clone the repo with 
```bash
git clone https://github.com/Mat-O-Lab/EnrichRdf
```
cd into the cloned folder
```bash
cd EnrichRdf
```
Build and start the container.
```bash
docker-compose up
```

A simple UI can be found at at the index page '/'
The API documentation at 'api/docs'
