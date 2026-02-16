# Textile Billing Web Application

A single-tenant web application for textile retail/wholesale fabric shops that handles textile-specific billing with GST, product and customer management, and printable/PDF invoices.

## Tech Stack

### Backend
- **Node.js** + **Express** + **TypeScript**
- **PostgreSQL** database with **Prisma** ORM
- **JWT** for authentication
- **bcrypt** for password hashing

### Frontend
- **React** + **TypeScript**
- **Vite** for build tooling
- **Ant Design** for UI components

## Project Structure

```
textile_app/
├── backend/          # Node.js/Express backend
│   ├── src/
│   │   ├── index.ts          # Express app entry point
│   │   ├── routes/           # API route handlers
│   │   ├── controllers/      # Business logic
│   │   ├── middlewares/      # Auth middleware, error handlers
│   │   └── config/           # Database config, env vars
│   ├── prisma/
│   │   └── schema.prisma     # Database schema
│   ├── package.json
│   └── tsconfig.json
├── frontend/         # React frontend
│   ├── src/
│   │   ├── main.tsx          # React app entry
│   │   ├── App.tsx
│   │   ├── pages/            # Page components
│   │   ├── components/       # Reusable components
│   │   └── services/         # API client
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Setup Instructions

### Prerequisites
- Node.js (v18 or higher)
- PostgreSQL (v12 or higher)
- npm or yarn

### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and update `DATABASE_URL` with your PostgreSQL connection string.

4. Set up database:
   ```bash
   # Generate Prisma Client
   npm run prisma:generate
   
   # Run migrations
   npm run prisma:migrate
   ```

5. Start development server:
   ```bash
   npm run dev
   ```

   The backend will run on `http://localhost:3000`

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

   The frontend will run on `http://localhost:5173` (or another port if 5173 is busy)

## Development Scripts

### Backend
- `npm run dev` - Start development server with hot reload
- `npm run build` - Build TypeScript to JavaScript
- `npm start` - Run production build
- `npm run prisma:generate` - Generate Prisma Client
- `npm run prisma:migrate` - Run database migrations
- `npm run prisma:studio` - Open Prisma Studio (database GUI)

### Frontend
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## API Endpoints (Planned)

- `POST /api/auth/login` - User login
- `GET /api/customers` - List customers
- `POST /api/customers` - Create customer
- `GET /api/products` - List products
- `POST /api/products` - Create product
- `GET /api/invoices` - List invoices
- `POST /api/invoices` - Create invoice
- `GET /api/invoices/:id` - Get invoice details

## Next Steps

See the plan document for detailed milestones:
1. ✅ Setup & skeleton
2. Auth + basic data models
3. Invoice creation
4. Invoice view/print
5. Polish and deploy

## Notes

- This is a single-tenant application designed for one textile shop
- The database schema is designed to be multi-tenant ready (can add `company_id` later if needed)
- Default authentication uses JWT tokens
- GST calculations are handled on the backend
