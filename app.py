from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from app import app

if __name__ == '__main__':
    app.run(debug=True)