# MVST Coffee Challenge ☕

> Full-stack coffee catalog application built with Next.js 13, NestJS, and PostgreSQL.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Docker Desktop (for PostgreSQL)

### Setup

```bash
# 1. Start PostgreSQL (requires Docker)
cd backend
npm run start:dev:db

# 2. Start the backend
npm run start:dev

# 3. Seed the database (first time only)
npm run seed

# 4. In a new terminal, start the frontend
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to see the app.

---

## 🛠 Tech Stack

### Backend
- **NestJS** - Chosen because MVST loves it and it provides excellent structure for APIs
- **TypeORM** - Great ORM for TypeScript, integrates perfectly with NestJS
- **PostgreSQL** - Robust relational database, perfect for this use case
- **class-validator** - For DTO validation (ensures clean data from the frontend)
- **Helmet** - Security middleware for HTTP headers (XSS, content-type sniffing, etc.)
- **@nestjs/throttler** - Rate limiting to prevent abuse

### Frontend
- **Next.js 13** (App Router) - Modern React framework with great DX
- **CSS Modules** - Pure CSS as requested, no Tailwind or component libraries
- **TypeScript** - Type safety across the entire codebase

### Why these choices?
I kept the stack minimal on purpose. The challenge asked to show CSS skills, so I avoided any CSS frameworks. TypeORM was chosen over Prisma because it integrates more naturally with NestJS decorators and the repository pattern. I added security middleware (Helmet + rate limiting) because even in a coding challenge, it's good practice to think about production concerns.

---

## 📁 Project Structure

```
coffee-challenge/
├── backend/
│   └── src/
│       ├── coffee/           # Coffee module
│       │   ├── coffee.entity.ts
│       │   ├── coffee.service.ts
│       │   ├── coffee.controller.ts
│       │   └── dto/
│       ├── app.module.ts     # Main module + DB config
│       ├── main.ts           # App bootstrap + CORS
│       └── seed.ts           # Database seeder
│
├── frontend/
│   └── src/
│       ├── app/              # Next.js app router
│       │   ├── page.tsx      # Main page
│       │   ├── layout.tsx    # Root layout + SEO
│       │   └── globals.css   # Design system
│       ├── components/       # React components
│       ├── services/         # API layer
│       └── types/            # TypeScript definitions
```

---

## ✨ Features Implemented

- [x] Coffee list fetched from backend API
- [x] Filter by type (All / Arabic / Robusta)
- [x] Add new coffee via modal form
- [x] Duplicate name validation (returns 409 Conflict)
- [x] Error toast notification
- [x] Responsive design (mobile + desktop)
- [x] CSS hover animations on cards
- [x] SEO meta tags
- [x] **Unit tests** (23 tests, 100% pass rate)

---

## 🔐 Security Considerations

Even though this is a coding challenge, I implemented security best practices:

- **Helmet** - Sets security-related HTTP headers (X-Content-Type-Options, X-Frame-Options, etc.)
- **Rate Limiting** - 10 requests per minute per IP to prevent API abuse
- **URL Validation** - Only `http://` and `https://` URLs are accepted (prevents `javascript:` XSS attacks)
- **Input Length Limits** - MaxLength on all string fields to prevent buffer overflow / DoS
- **Price Validation** - Min/Max validators to ensure reasonable values
- **Input Validation** - All DTOs are validated with class-validator before processing
- **CORS** - Configured to only accept requests from the frontend origin
- **Whitelist** - ValidationPipe strips unknown properties from requests

---

## 🎨 Design Decisions

**Validation on both sides**: The backend validates with `class-validator` that the coffee type is either "Arabic" or "Robusta", and the DTO ensures all required fields are present. The frontend also validates before submission.

**Error handling**: When a duplicate name is detected, the backend throws a `ConflictException` (409). The frontend catches this and shows a toast notification rather than crashing.

**Component architecture**: Each component is self-contained with its own CSS module. This makes them reusable and easy to maintain.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/coffees` | List all coffees |
| GET | `/coffees?type=Arabic` | Filter by type |
| POST | `/coffees` | Create new coffee |

### Create Coffee Request Body
```json
{
  "name": "Espresso",
  "description": "Strong and bold",
  "type": "Arabic",
  "price": 15.00,
  "imageUrl": "https://example.com/coffee.jpg"
}
```

---

## 🧪 Testing

Run tests with:
```bash
cd backend
npm test
```

**Test Coverage:**
- `CoffeeService` - Business logic tests (findAll, create, duplicate validation)
- `CoffeeController` - API endpoint tests
- `CreateCoffeeDto` - Input validation tests including XSS prevention

All 23 tests passing ✅

---

## Feedback

### What would you improve if given more time?

1. **E2E tests** - Add integration tests with supertest to verify full request/response cycles
2. **Image upload** - Instead of just URLs, implement actual file upload with preview
3. **Pagination** - For larger coffee lists with infinite scroll
4. **Edit/Delete** - Complete CRUD operations with confirmation dialogs
5. **Environment variables** - Move DB credentials to .env file for production
6. **Docker Compose** - Single command to spin up the entire stack

### How was your experience doing this challenge?

Really enjoyed it! The Figma design was clear and the requirements were well-defined. I appreciated that the boilerplate was provided but still gave freedom to structure things my own way. The NestJS + Next.js combo works great together. I took extra time to add security features (Helmet, rate limiting, input validation) because I believe even coding challenges should reflect production-quality thinking.

---

## 🚀 Deployment

The application is configured for deployment on **Render.com** (free tier).

### Environment Variables

**Backend:**
- `DATABASE_URL` - PostgreSQL connection string
- `FRONTEND_URL` - Frontend URL for CORS
- `PORT` - Server port (default: 5000)

**Frontend:**
- `NEXT_PUBLIC_API_URL` - Backend API URL

### Docker Support

Both backend and frontend include Dockerfiles for containerized deployment:
```bash
# Build backend
cd backend && docker build -t coffee-backend .

# Build frontend
cd frontend && docker build -t coffee-frontend .
```

### Live Demo
🔗 **[View Live Demo](https://coffee-frontend.onrender.com)** *(if deployed)*

---

## 📝 Notes

- The database runs on `localhost:5432` via Docker (local development)
- Backend serves on `http://localhost:5000`
- Frontend serves on `http://localhost:3000`
- CORS is configured to allow frontend-backend communication
- In production, environment variables configure all URLs

---

Thanks for the challenge! 🔥


