#!/bin/bash

# Spiritual Voice Bot - Quick Start Script
echo "Starting Spiritual Voice Bot..."
echo ""

# Check if setup has been run
if [ ! -d "backend/venv" ] && [ ! -d "frontend/node_modules" ]; then
    echo "First time setup required. Running setup..."
    ./setup.sh
    echo ""
fi

# Start with Docker if docker-compose is available
if command -v docker-compose &> /dev/null; then
    echo "Starting with Docker Compose..."
    docker-compose up -d
    echo ""
    echo "Services started!"
    echo "Frontend: http://localhost:3000"
    echo "Backend API: http://localhost:8080"
    echo "API Docs: http://localhost:8080/docs"
    echo ""
    echo "To view logs: docker-compose logs -f"
    echo "To stop: docker-compose down"
else
    echo "Docker Compose not found. Starting manually..."
    echo ""

    # Start backend
    echo "Starting backend..."
    cd backend
    source venv/bin/activate 2>/dev/null || . venv/bin/activate
    uvicorn main:app --reload &
    BACKEND_PID=$!
    cd ..
    echo "Backend started (PID: $BACKEND_PID)"

    # Wait for backend to start
    sleep 5

    # Start frontend
    echo "Starting frontend..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    echo "Frontend started (PID: $FRONTEND_PID)"

    echo ""
    echo "Services started!"
    echo "Frontend: http://localhost:3000"
    echo "Backend API: http://localhost:8080"
    echo ""
    echo "Press Ctrl+C to stop all services"

    # Wait for user interrupt
    wait
fi
