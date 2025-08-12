# Django Backend API

This is the backend for a web application that helps users study by providing features like creating courses, uploading topics (PDFs), and generating summaries, flashcards, and quizzes from the uploaded content. It uses Django and Django Ninja for the REST API.

## Getting Started

### Prerequisites

*   Python 3.12
*   PostgreSQL
*   Cloudinary Account
*   Groq API Key

### Installation

1.  Clone the repository.
2.  Navigate to the `backend` directory.
3.  Create a virtual environment:
    ```bash
    python -m venv venv
    ```
4.  Activate the virtual environment:
    *   **Windows:**
        ```bash
        venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```
5.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
6.  Create a `.env` file in the `backend` directory and add the following environment variables:
    ```
    SECRET_KEY=your_django_secret_key
    DB_NAME=your_db_name
    DB_USER=your_db_user
    DB_PASSWORD=your_db_password
    DB_HOST=localhost
    DB_PORT=5432
    CLOUDINARY_CLOUD_NAME=your_cloudinary_cloud_name
    CLOUDINARY_API_KEY=your_cloudinary_api_key
    CLOUDINARY_API_SECRET=your_cloudinary_api_secret
    GROQ_API_KEY=your_groq_api_key
    ```
7.  Generate JWT signing keys:
    ```bash
    openssl genpkey -algorithm RSA -out jwt-signing.pem -pkeyopt rsa_keygen_bits:2048
    openssl rsa -pubout -in jwt-signing.pem -out jwt-signing.pub
    ```
8.  Run database migrations:
    ```bash
    python manage.py migrate
    ```

## Usage

Run the development server:

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/api/`.

## API Endpoints

*   `api/auth/register`: Register a new user.
*   `api/auth/token/`: Obtain a JWT token.
*   `api/auth/me`: Get the current user's information.
*   `api/courses/`:
    *   `GET`: List all courses for the authenticated user.
    *   `POST`: Create a new course.
*   `api/courses/{course_id}/`:
    *   `GET`: Get a specific course.
    *   `PATCH`: Update a specific course.
    *   `DELETE`: Delete a specific course.
*   `api/courses/{course_id}/topics`:
    *   `GET`: List all topics for a specific course.
    *   `POST`: Create a new topic for a specific course.
*   `api/topics/{topic_id}`:
    *   `GET`: Get a specific topic.
    *   `PATCH`: Update a specific topic.
    *   `DELETE`: Delete a specific topic.
*   `api/topics/{topic_id}/summary`: Generate a summary for a topic.
*   `api/topics/{topic_id}/flashcards`: Generate flashcards for a topic.
*   `api/topics/{topic_id}/quiz`: Generate a quiz for a topic.
*   `api/topics/{topic_id}/quiz-flashcards`: Generate both a quiz and flashcards for a topic.
*   `api/topics/{topic_id}/progress`: Update the progress of a topic.

## Models

*   **Item**: An example model.
*   **Course**: Represents a course created by a user.
*   **Topic**: Represents a topic within a course, which can have a file attached.

## Dependencies

*   Django
*   django-ninja
*   psycopg2-binary
*   python-dotenv
*   django-cors-headers
*   django-ninja-simple-jwt
*   cloudinary
*   django-cloudinary-storage
*   PyMuPDF
*   requests
*   groq
*   ollama
