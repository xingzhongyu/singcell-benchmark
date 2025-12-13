(1)将所有算法改造为docker(FastAPI)
(2)重启backend，将其改造为docker，同时对前后端进行改造
(3)将算法接入backend


conda activate scanpy-app-backend
cd backend/
uvicorn app.main:app --reload


conda activate scanpy-app-backend
cd backend/
celery -A celery_app worker --loglevel=info


conda activate scanpy-app-frontend
cd frontend/
npm start