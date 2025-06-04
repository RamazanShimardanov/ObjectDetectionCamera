import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Now we can import from the server directory
from server.server import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)