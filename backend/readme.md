redis-server

conda activate scanpy-app-backend
celery -A celery_app.celery_app worker --loglevel=info -P solo # -P solo for Windows compatibility if needed


conda activate scanpy-app-frontend
npm start
# or: yarn start


conda activate scanpy-app-backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000