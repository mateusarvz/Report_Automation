# Report Psicologia

## Estrutura
- `app/`: backend Python FastAPI
- `frontend/`: frontend React + Vite
- `templates/`, `static/`: frontend estático original e templates Jinja usados pelo backend
- `Relatorios_Metricas/`: relatórios customizados

## Passos para rodar

### Backend Python
1. `cd c:\Users\Mateus\Desktop\PythonApps\Report_Psicologia`
2. `.venv\Scripts\Activate.ps1`
3. `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

### Frontend React
1. `cd c:\Users\Mateus\Desktop\PythonApps\Report_Psicologia\frontend`
2. `npm install`
3. `npm run dev`

### Produção local
1. `cd c:\Users\Mateus\Desktop\PythonApps\Report_Psicologia\frontend`
2. `npm run build`
3. `node frontend/server.js`

### Testes Python
1. `cd c:\Users\Mateus\Desktop\PythonApps\Report_Psicologia`
2. `.venv\Scripts\Activate.ps1`
3. `pytest -q`
