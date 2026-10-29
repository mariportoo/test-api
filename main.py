from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Task Manager API", version="1.0.0")

# 1. Define the data schema for incoming POST requests
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None

class Task(TaskCreate):
    id: int

# 2. In-memory storage acting as a temporary database
fake_db: List[dict] = [
    {"id": 1, "title": "Buy groceries", "description": "Milk, eggs, coffee"},
    {"id": 2, "title": "Inspect tires", "description": "Check tire pressure"},
]

# 3. GET Method: Retrieve all tasks
@app.get("/tasks", response_model=List[Task], status_code=status.HTTP_200_OK)
def get_all_tasks():
    return fake_db

# 4. GET Method: Retrieve a single task by ID
@app.get("/tasks/{task_id}", response_model=Task, status_code=status.HTTP_200_OK)
def get_task(task_id: int):
    for task in fake_db:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")

# 5. POST Method: Create a new task
@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(task_in: TaskCreate):
    # Auto-generate a simple numeric ID
    new_id = (max([t["id"] for t in fake_db], default=0)) + 1
    new_task = {"id": new_id, **task_in.model_dump()}
    fake_db.append(new_task)
    return new_task

# 6. DELETE Method: Remove a task by ID
@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    for index, task in enumerate(fake_db):
        if task["id"] == task_id:
            fake_db.pop(index)
            return None  # 204 No Content expects an empty body
    raise HTTPException(status_code=404, detail="Task not found")