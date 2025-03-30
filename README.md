# TrustLink Backend

Backend API for TrustLink - a mobile application for communication between citizens and law enforcement.

## Features

- **User Authentication**: Secure JWT-based authentication with role-based access control
- **Incident Reporting**: Citizens can report incidents with location data and track status updates
- **Real-time Chat**: WebSocket-based real-time chat between citizens and police
- **Emergency Button**: Direct connection to nearest police station in emergencies
- **File Attachments**: Support for uploading images, videos, and documents
- **Data Security**: Comprehensive security measures for protecting sensitive user data

## Tech Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **PostgreSQL**: Powerful, open-source relational database
- **SQLAlchemy**: SQL toolkit and ORM for database operations
- **WebSockets**: For real-time communication
- **JWT Authentication**: Secure, stateless authentication
- **Redis**: For caching and WebSocket scaling
- **Pydantic**: Data validation and settings management
- **Alembic**: Database migrations

## Development Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- Redis 6+

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/trustlink-backend.git
   cd trustlink-backend
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory with the following content:
   ```
   POSTGRES_SERVER=localhost
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=trustlink
   POSTGRES_PORT=5432
   
   SECRET_KEY=your_secret_key
   
   CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
   ```

5. Create the database:
   ```
   createdb trustlink  # Using PostgreSQL CLI
   ```

6. Run migrations:
   ```
   alembic upgrade head
   ```

7. Start the server:
   ```
   uvicorn main:app --reload
   ```

The API will be available at http://localhost:8000/api.
API documentation will be available at http://localhost:8000/api/docs.

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login to get access token

### Users
- `GET /api/users/me` - Get current user info
- `PUT /api/users/me` - Update current user
- `GET /api/users` - List all users (admin only)

### Incidents
- `POST /api/incidents` - Create a new incident
- `GET /api/incidents` - Get all incidents
- `GET /api/incidents/{id}` - Get specific incident
- `PUT /api/incidents/{id}` - Update incident status

### Chat
- `GET /api/chat/incidents/{id}/messages` - Get messages for an incident
- `POST /api/chat/messages` - Create a new message
- `POST /api/chat/emergency` - Send emergency message
- `WebSocket /api/ws/chat/{incident_id}` - Real-time chat connection

## WebSocket Message Format

### Sending Messages
```json
{
  "type": "message",
  "content": "Your message here"
}
```

### Status Updates
```json
{
  "type": "typing",
  "is_typing": true
}
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 