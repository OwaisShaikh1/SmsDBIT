# SMS Portal - Setup & Installation Guide

## 🚀 Project Overview

A modern web portal built with React (frontend) and Django REST Framework (backend) that integrates with MySMSMantra Bulk SMS API for sending messages.

## 📋 Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

## 🛠️ Backend Setup (Django)

### 1. Navigate to Backend Directory
```bash
cd backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment
**Windows:**
```bash
.\venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Configuration
```bash
cp .env.example .env
```

Edit `.env` file with your configurations:
```env
SECRET_KEY=your-super-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# MySMSMantra API Configuration
MYSMSMANTRA_API_KEY=your-api-key-here
MYSMSMANTRA_CLIENT_ID=your-client-id-here
MYSMSMANTRA_SENDER_ID=your-sender-id-here

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 6. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 8. Start Development Server
```bash
python manage.py runserver
```

Backend will be available at: **http://127.0.0.1:8000/**

## 🎨 Frontend Setup (React)

### 1. Navigate to Frontend Directory
```bash
cd frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Environment Configuration
Create `.env` file:
```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_APP_NAME=SMS Portal
```

### 4. Start Development Server
```bash
npm run dev
```

Frontend will be available at: **http://localhost:5173/**

## 🔧 API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/token/refresh/` - Token refresh
- `GET /api/auth/profile/` - Get user profile

### SMS Operations
- `POST /api/send-sms/` - Send single SMS
- `POST /api/bulk-send/` - Bulk SMS sending
- `GET /api/history/` - SMS history
- `GET /api/history/{id}/` - SMS detail

### Management
- `GET/POST /api/templates/` - Template management
- `GET/POST /api/senders/` - Sender ID management
- `GET/PATCH /api/credentials/` - API credentials
- `GET /api/dashboard/` - Dashboard statistics

## 📱 MySMSMantra API Integration

The system integrates with MySMSMantra API using the following endpoint format:
```
https://api.mylogin.co.in/api/v2/SendSMS?ApiKey={ApiKey}&ClientId={ClientId}&SenderId={SenderId}&Message={Message}&MobileNumbers={Numbers}&Is_Unicode=0&Is_Flash=0
```

## 🧪 Testing

### Backend API Testing
Use the provided `api_test.http` file with VS Code REST Client extension or similar tools.

### Frontend Testing
```bash
cd frontend
npm run build
```

## 🚀 Production Deployment

### Backend
1. Set `DEBUG=False` in production
2. Configure proper database (PostgreSQL recommended)
3. Set up proper secret key
4. Configure CORS and ALLOWED_HOSTS
5. Use a WSGI server (Gunicorn, uWSGI)

### Frontend
```bash
npm run build
```
Deploy the `dist` folder to your web server.

## 🔐 Security Features

- JWT Authentication with automatic token refresh
- User input validation
- CORS protection
- Password validation
- Secure API credential storage

## 📊 Key Features

- 🔐 JWT Authentication
- 📱 Single & Bulk SMS sending
- 📝 Template management
- 👤 Sender ID management
- 📊 Usage statistics & analytics
- ⚙️ API credentials configuration
- 📱 Responsive design
- 🎨 Modern UI with Tailwind CSS

## 🐛 Troubleshooting

### Common Issues

1. **Port conflicts**: Change ports in configuration if needed
2. **CORS errors**: Ensure CORS_ALLOWED_ORIGINS includes your frontend URL
3. **Database errors**: Run migrations after model changes
4. **API key errors**: Verify MySMSMantra credentials

### Support

For issues or questions, check the API testing file and ensure all environment variables are properly configured.

---

Built with ❤️ using Django REST Framework and React