(.venv) PS C:\Users\Cicada38\Projects\compliance-EU> python src\app.py
C:\Users\Cicada38\Projects\compliance-EU\src\app.py:54: DeprecationWarning: 
        on_event is deprecated, use lifespan event handlers instead.

        Read more about it in the
        [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

  @app.on_event("startup")
C:\Users\Cicada38\Projects\compliance-EU\src\app.py:96: DeprecationWarning: 
        on_event is deprecated, use lifespan event handlers instead.

        Read more about it in the
        [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

  @app.on_event("shutdown")
{"event": "Started server process [13124]"}
{"event": "Waiting for application startup."}
{"event": "{\"version\": \"1.0.0\", \"event\": \"Starting Compliance Automation Kit\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.163231Z\", \"func_name\": \"startup_event\"}"}
{"event": "{\"event\": \"Initializing database\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.163231Z\", \"func_name\": \"init_database\"}"}  
{"event": "{\"event\": \"Database initialized successfully\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.164231Z\", \"func_name\": \"init_database\"}"}
{"event": "{\"event\": \"Database initialized successfully\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.164231Z\", \"func_name\": \"startup_event\"}"}
{"event": "{\"event\": \"Scheduler loop started\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.165230Z\", \"func_name\": \"_run_scheduler\"}"}
{"event": "{\"check_interval\": 60, \"event\": \"Scheduler started\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.165230Z\", \"func_name\": \"start\"}"}
{"event": "{\"scheduled_datasets\": 0, \"total_datasets\": 3, \"event\": \"Scheduler initialized\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:37.171739Z\", \"func_name\": \"startup_event\"}"}
{"event": "Application startup complete."}
{"event": "Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)"}



(.venv) PS C:\Users\Cicada38\Projects\compliance-EU> python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
INFO:     Will watch for changes in these directories: ['C:\\Users\\Cicada38\\Projects\\compliance-EU']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [22976] using WatchFiles
{"event": "Started server process [33668]"}
{"event": "Waiting for application startup."}
{"event": "{\"version\": \"1.0.0\", \"event\": \"Starting Compliance Automation Kit\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.935446Z\", \"func_name\": \"startup_event\"}"}
{"event": "{\"event\": \"Initializing database\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.935446Z\", \"func_name\": \"init_database\"}"}  
{"event": "{\"event\": \"Database initialized successfully\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.936446Z\", \"func_name\": \"init_database\"}"}
{"event": "{\"event\": \"Database initialized successfully\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.936446Z\", \"func_name\": \"startup_event\"}"}
{"event": "{\"event\": \"Scheduler loop started\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.937692Z\", \"func_name\": \"_run_scheduler\"}"}
{"event": "{\"check_interval\": 60, \"event\": \"Scheduler started\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.937692Z\", \"func_name\": \"start\"}"}
{"event": "{\"scheduled_datasets\": 0, \"total_datasets\": 3, \"event\": \"Scheduler initialized\", \"level\": \"info\", \"timestamp\": \"2025-09-04T01:37:52.943696Z\", \"func_name\": \"startup_event\"}"}
{"event": "Application startup complete."}


This site can’t be reached
The webpage at http://0.0.0.0:8000/ might be temporarily down or it may have moved permanently to a new web address.
ERR_ADDRESS_INVALID