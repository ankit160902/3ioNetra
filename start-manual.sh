#!/bin/bash

# Spiritual Voice Bot - Manual Start (No Docker Required)
echo "=========================================="
echo "Spiritual Voice Bot - Manual Startup"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    echo "   Mac: brew install python@3.10"
    echo "   Ubuntu: sudo apt install python3.10"
    exit 1
fi
echo "✓ Python found: $(python3 --version)"

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    echo "   Mac: brew install node"
    echo "   Ubuntu: sudo apt install nodejs npm"
    exit 1
fi
echo "✓ Node.js found: $(node --version)"

# Check ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg not found. Voice features may not work."
    echo "   Install: brew install ffmpeg (Mac) or sudo apt install ffmpeg (Linux)"
else
    echo "✓ ffmpeg found"
fi

echo ""

# Check if backend is set up
if [ ! -d "backend/venv" ]; then
    echo "Backend not set up. Running first-time setup..."
    echo ""

    cd backend

    echo "Creating virtual environment..."
    python3 -m venv venv

    echo "Activating virtual environment..."
    source venv/bin/activate

    echo "Installing Python dependencies (this may take 5-10 minutes)..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet

    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo "✓ Created .env file"
    fi

    cd ..
    echo "✓ Backend setup complete!"
    echo ""
fi

# Check if frontend is set up
if [ ! -d "frontend/node_modules" ]; then
    echo "Frontend not set up. Running first-time setup..."
    echo ""

    cd frontend

    echo "Installing Node dependencies (this may take 3-5 minutes)..."
    npm install --silent

    if [ ! -f ".env.local" ]; then
        echo "NEXT_PUBLIC_API_URL=http://localhost:8080" > .env.local
        echo "✓ Created .env.local file"
    fi

    cd ..
    echo "✓ Frontend setup complete!"
    echo ""
fi

# Create log directory
mkdir -p logs

echo "=========================================="
echo "Starting Services"
echo "=========================================="
echo ""

# Start backend
echo "Starting Backend..."
cd backend
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8080 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"
echo "  Logs: logs/backend.log"
cd ..

# Wait for backend to start
echo "  Waiting for backend to initialize..."
sleep 3

# Check if backend is running
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✓ Backend is healthy!"
else
    echo "⚠️  Backend may not be ready yet (this is normal on first start)"
    echo "  Give it 10-20 seconds and check: http://localhost:8080/health"
fi

echo ""

# Start frontend
echo "Starting Frontend..."
cd frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✓ Frontend started (PID: $FRONTEND_PID)"
echo "  Logs: logs/frontend.log"
cd ..

echo ""

# Wait for frontend to start
echo "  Waiting for frontend to initialize..."
sleep 5

echo ""
echo "=========================================="
echo "Services Started!"
echo "=========================================="
echo ""
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend:  http://localhost:8080"
echo "📚 API Docs: http://localhost:8080/docs"
echo ""
echo "📊 View Logs:"
echo "  Backend:  tail -f logs/backend.log"
echo "  Frontend: tail -f logs/frontend.log"
echo ""
echo "🛑 Stop Services:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
echo "  Or run: ./stop-manual.sh"
echo ""
echo "💡 First-time model downloads may take a few minutes"
echo "   The first query will be slower (30-60 seconds)"
echo ""
echo "=========================================="
echo ""

# Save PIDs for stopping later
echo "$BACKEND_PID" > logs/backend.pid
echo "$FRONTEND_PID" > logs/frontend.pid

# Open browser (optional)
read -p "Open browser now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sleep 2
    if command -v open &> /dev/null; then
        open http://localhost:3000
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:3000
    else
        echo "Please open http://localhost:3000 in your browser"
    fi
fi

echo ""
echo "✨ Enjoy your Spiritual Voice Bot!"
echo "🙏 Om Shanti Shanti Shanti"
echo ""
