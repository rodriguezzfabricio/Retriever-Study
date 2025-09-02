# Retriever Study - AI-Powered Study Group Finder

## PROJECT OVERVIEW
This is an AI-powered study group finder application that connects students based on their study preferences, subjects, and learning goals using advanced AI embeddings and natural language processing.

**Tech Stack:**
- Frontend: React with React Router
- Backend: FastAPI with async/await
- Database: SQLite (local development)
- AI/ML: sentence-transformers, transformers library
- Deployment: AWS Lambda (backend), S3+CloudFront (frontend)

## CURRENT PROJECT STATUS

### ✅ COMPLETED TASKS
1. **Backend Core Infrastructure**
   - ✅ FastAPI app with health endpoint (`/backend/app/main.py`)
   - ✅ SQLite database with threading fixes (`/backend/app/data/local_db.py`)
   - ✅ AI embeddings module (`/backend/app/core/embeddings.py`)
   - ✅ Toxicity filtering (`/backend/app/core/toxicity.py`)

2. **Backend API Endpoints**
   - ✅ `/health` - Health check
   - ✅ `/users` - User CRUD operations
   - ✅ `/groups` - Group CRUD operations
   - ✅ `/recommendations/{user_id}` - AI-powered group recommendations
   - ✅ `/search` - Vector-based group search
   - ✅ `/groups/{group_id}/messages` - Message posting with toxicity filtering
   - ✅ `/groups/{group_id}/messages/summary` - AI chat summarization

3. **Frontend Foundation**
   - ✅ React project setup with dependencies (`/frontend/package.json`)
   - ✅ API service layer (`/frontend/src/services/api.js`)
   - ✅ Zara-inspired Header component (`/frontend/src/components/Header.js`)
   - ✅ Navigation component (`/frontend/src/components/Navigation.js`)
   - ✅ Layout wrapper (`/frontend/src/components/Layout.js`)
   - ✅ App routing setup (`/frontend/src/App.js`)
   - ✅ Group card component (`/frontend/src/components/GroupCard.js`)

### 🔄 CURRENTLY IN PROGRESS
4. **Groups List Page** - Creating the main groups listing with recommendations and search

### 📋 REMAINING TASKS (IN ORDER)
5. **Group Detail Page** - Chat interface with summarization
6. **Profile Page** - User management interface
7. **Login Page** - User authentication
8. **End-to-End Testing** - Full functionality verification
9. **AWS Lambda Packaging** - Backend deployment preparation
10. **S3+CloudFront Deployment** - Frontend deployment
11. **Documentation** - Final documentation and proof materials

## DETAILED TASK BREAKDOWN

### Task 4: Groups List Page (IN PROGRESS)
**Location:** `/frontend/src/pages/GroupsList.js`
**Requirements:**
- Display recommended groups using `/recommendations/{user_id}` API
- Display search results using `/search` API
- Show all groups by default using `/groups` API
- Implement join group functionality
- Zara-inspired grid layout
- Handle different modes: all groups, recommendations, search
- Props: `searchQuery`, `showRecommendations`, `showSearch`

**Components needed:**
- Main GroupsList component
- Group grid layout
- Loading states
- Error handling
- Search input integration

### Task 5: Group Detail Page
**Location:** `/frontend/src/pages/GroupDetail.js`
**Requirements:**
- Display group information
- Real-time chat interface
- Message posting with toxicity filtering
- Chat summarization feature
- Member list display
- Join/leave group functionality
- Connect to `/groups/{id}`, `/groups/{id}/messages`, `/groups/{id}/messages/summary`

### Task 6: Profile Page
**Location:** `/frontend/src/pages/Profile.js`
**Requirements:**
- User information display
- Edit profile functionality
- Joined groups list
- User preferences management
- Connect to `/users/{id}` endpoints

### Task 7: Login Page
**Location:** `/frontend/src/pages/Login.js`
**Requirements:**
- User authentication form
- Create new user functionality
- Form validation
- Redirect to groups page after login
- Connect to `/users` POST endpoint

### Task 8: End-to-End Testing
**Requirements:**
- Test user creation and login
- Test group recommendations
- Test search functionality
- Test group joining and chat
- Test message posting and toxicity filtering
- Test chat summarization
- Verify all API connections work
- Test responsive design

### Task 9: AWS Lambda Packaging
**Location:** `/backend/`
**Requirements:**
- Create Lambda deployment package
- Update database configuration for AWS
- Environment variable setup
- Requirements.txt optimization
- Handler function creation

### Task 10: S3+CloudFront Deployment
**Location:** `/frontend/`
**Requirements:**
- Build production React app
- S3 bucket configuration
- CloudFront distribution setup
- Environment variable configuration for production API

### Task 11: Documentation
**Requirements:**
- README.md with setup instructions
- API documentation
- Deployment guide
- Architecture overview
- Screenshots and demos

## CRITICAL TECHNICAL NOTES

### Database Schema
```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    bio TEXT,
    interests TEXT,  -- JSON array
    embedding BLOB   -- Pickled numpy array
)

-- Groups table  
CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    subject TEXT,
    embedding BLOB   -- Pickled numpy array
)

-- Messages table
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER,
    user_id INTEGER,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    toxicity_score REAL,
    FOREIGN KEY (group_id) REFERENCES groups (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
)
```

### AI Pipeline
1. **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 model
2. **Recommendations**: Cosine similarity between user and group embeddings
3. **Search**: Vector similarity search with text queries
4. **Toxicity**: unitary/toxic-bert for content filtering
5. **Summarization**: Built-in transformers summarization pipeline

### API Service Pattern
All frontend API calls go through `/frontend/src/services/api.js`:
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
// Centralized error handling, URL encoding, JSON parsing
```

### Component Architecture
- **Layout Components**: Header, Navigation, Layout wrapper
- **Page Components**: GroupsList, GroupDetail, Profile, Login
- **UI Components**: GroupCard, SearchBar, MessageList, etc.
- **Services**: API layer, utilities

### Styling Approach
- Component-specific CSS files
- Zara-inspired minimal design
- Responsive breakpoints at 768px
- Clean typography with uppercase labels
- Black/white/gray color scheme

## COMMON PITFALLS TO AVOID

1. **SQLite Threading**: Always create new connections, never reuse across threads
2. **API Error Handling**: Always wrap API calls in try/catch
3. **React Keys**: Use unique keys for mapped components
4. **State Updates**: Use functional updates for state that depends on previous state
5. **Route Parameters**: Use useParams() hook for dynamic routes
6. **Environment Variables**: Prefix React env vars with REACT_APP_
7. **CORS**: Backend already configured for frontend origin
8. **Model Loading**: AI models are cached on first load for performance

## SUCCESS CRITERIA

The project is complete when:
- ✅ Backend health endpoint returns 200
- ✅ All API endpoints functional and tested
- ✅ Frontend displays groups with Zara-inspired design  
- ✅ Recommendations work based on user embeddings
- ✅ Search finds relevant groups
- ✅ Group chat with toxicity filtering works
- ✅ Chat summarization generates meaningful summaries
- ✅ Responsive design works on mobile
- ✅ End-to-end user flow: login → browse → join → chat → summarize
- ✅ Deployable to AWS

## EMERGENCY CONTACTS / DEBUGGING

### Backend Server
```bash
cd /backend
source venv/bin/activate  
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Development
```bash
cd /frontend
npm start  # Runs on port 3000 with proxy to backend
```

### Database Reset
```bash
rm /backend/app/data/retriever_study.db  # Deletes and recreates on next start
```

### Key Files for Quick Reference
- Main API: `/backend/app/main.py`
- Database: `/backend/app/data/local_db.py` 
- AI Core: `/backend/app/core/embeddings.py`
- Frontend API: `/frontend/src/services/api.js`
- Routing: `/frontend/src/App.js`

**Last Updated:** Current session - Task 4 (Groups List Page) in progress