# GitHub Organization Mailer

A web application that allows sending emails to all members of a GitHub organization.

## Project Structure
```
github-org-mailer/
├── backend/           # Go backend
│   ├── main.go       # Main server file
│   └── mail/         # Email handling package
│       └── mail.go
└── frontend/         # Vue.js frontend
    ├── index.html
    └── src/
        └── main.js
```

## Setup

### Backend Setup

1. Set the following environment variables:
```bash
export GITHUB_TOKEN="your-github-token"
export GITHUB_ORG="your-org-name"
export SMTP_HOST="your-smtp-host"
export SMTP_PORT="your-smtp-port"
export SMTP_USER="your-smtp-username"
export SMTP_PASS="your-smtp-password"
export FROM_EMAIL="your-from-email"
```

2. Install dependencies and run the backend:
```bash
cd backend
go mod tidy
go run main.go
```

The backend server will start on http://localhost:3000

### Frontend Setup

1. Simply serve the frontend directory using any static file server. For example:
```bash
cd frontend
python3 -m http.server 8080
```

The frontend will be available at http://localhost:8080

## API Endpoints

- `GET /api/members`: Get all members of the GitHub organization
- `POST /api/send-mail`: Send email to all organization members
  - Request body:
    ```json
    {
      "subject": "Email subject",
      "body": "Email body"
    }
    ```

## Required Permissions

1. GitHub Token needs the following permissions:
   - `read:org` to list organization members
   - `user:email` to get member email addresses

2. SMTP credentials with permission to send emails
