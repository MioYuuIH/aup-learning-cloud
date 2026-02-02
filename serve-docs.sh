#!/bin/bash
# Serve documentation locally for testing

PORT=${1:-8888}

echo "🔨 Building documentation..."
make html

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "🚀 Starting documentation server on port $PORT..."
    echo "📚 Open in browser: http://localhost:$PORT"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""

    python3 -m http.server $PORT --directory build/html
else
    echo ""
    echo "❌ Build failed. Please check the errors above."
    exit 1
fi
