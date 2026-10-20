# Operations & SRE Runbook
## Construction Logistics Platform (SitePulse)

This runbook outlines operational procedures, health monitoring, deployment commands, and incident response runbooks for operating the SitePulse Construction Logistics Platform.

---

## 1. Quickstart & Service Management

### Local Development
```bash
# 1. Complete stack launch (FastAPI on :8000 + Streamlit on :8501)
./start.sh

# 2. Or start individual services:
# API server with hot-reload:
python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Streamlit Analytics Dashboard:
python3 -m streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1
```

### Docker Compose (Full Stack with PostgreSQL)
```bash
# Setup environment and launch containers
cp .env.example .env
docker compose up --build -d

# Check service health status
docker compose ps

# Follow centralized application logs
docker compose logs -f api
```

---

### Railway synthetic demo

Use `shokkanuly/delivery-delay` for both services, with the repository-root Dockerfile.
The API serves the product console at `/`; Streamlit is the separate analyst service.
Railway hosts the synthetic demo only. Real customer data belongs in the Kazakhstan/on-premise
deployment described in `docs/plans/mvp-reshape.md`.

After deploying a revision containing the startup scripts, configure:

| Service | Start command | Health path | Port |
| :--- | :--- | :--- | :--- |
| API | `sh scripts/start_api.sh` | `/health` | `PORT=8080` |
| Analyst dashboard | `sh scripts/start_dashboard.sh` | `/_stcore/health` | `PORT=8080` |

Use a 300-second health-check timeout for the API's first model load. Keep the API's existing
`DATABASE_URL` connected to its persistent Postgres service. Generate an admin key once in the
API variables; reference that same value from the dashboard as
`SITEPULSE_ADMIN_KEY=${{logistics-api.SITEPULSE_ADMIN_KEY}}`. The dashboard also needs
`API_URL=http://logistics-api.railway.internal:8080`. Set `PYTHONUNBUFFERED=1` on both services
and `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` on the API.

If the deployed revision predates these scripts, the equivalent API command is:

```sh
sh -c 'exec python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}'
```

For the dashboard:

```sh
sh -c 'exec python -m streamlit run dashboard/app.py --server.port ${PORT:-8080} --server.address 0.0.0.0 --server.headless true'
```

Do not pass literal `$PORT` directly to a Dockerfile service's custom command: Railway uses
exec form, which does not expand variables. See the [Railway start-command documentation](https://docs.railway.com/deployments/start-command).
The scripts expand the value inside a shell and replace the shell with the server process.
Do not run `db.seed` on each deployment; API startup already seeds an empty demo database.

Review the production environment's staged changes and deploy them. Verify both Railway
deployment states are successful, then request the public API's `/health`, the console `/`,
and the dashboard's `/_stcore/health`. Health paths are service-specific; do not place the
dashboard health path in the shared root `railway.json`.

### Аудит выгрузки 1С

Откройте `http://localhost:8000/#audit`, выберите CSV и введите свой `SITEPULSE_ADMIN_KEY`.
Ключ не внедряется в HTML, не записывается в localStorage и очищается после запроса.
Кнопка «Печать / сохранить PDF» печатает только отчёт без формы и навигации.

Ограничения: 5 МБ, 10 000 входных строк, один аудит одновременно на процесс API.
Кодировки UTF-8/Windows-1251, разделители запятая/точка с запятой/табуляция.
Дата может быть ISO `YYYY-MM-DD` или формата 1С `DD.MM.YYYY`, включая смешанные столбцы.
XLSX нужно сначала сохранить как CSV. Синтетический пример доступен по
`/static/samples/1c_export_synthetic.csv`.

```sh
curl --fail-with-body -X POST http://localhost:8000/audit/history \
  -H "X-API-Key: $SITEPULSE_ADMIN_KEY" \
  -F synthetic=true \
  -F file=@tests/fixtures/1c_export_cp1251.csv
```

Ответ содержит `quality`, `scorecard`, `material_breakdown` и `backtest`.
`synthetic=true` явно маркирует синтетику; без него происхождение истории считается непроверенным.
Маршрут из экспорта заменяется на `unknown` и учитывается в отчёте качества. Точные русские
имена материалов используют общие допуски из `ml/labeling.py`; неизвестная номенклатура сохраняет
свой исходный текст и получает явно посчитанный допуск по умолчанию (1 день).

Проверка модели: первые 70% заказов против последних 30%, без разделения одинаковых дат заказа.
Из обучения исключаются поставки, не завершённые до первого проверочного заказа; из проверки
хронологии — поступления/плановые даты раньше заказа. Модель и снимок признаков создаются только
в памяти из обучающей части. Ни действующий `model.joblib`, ни его кеш, ни таблицы БД не меняются.
Минимум: 50 обучающих и 20 проверочных поставок, обе категории исхода; при недостатке данных
возвращается `insufficient_data`, а карточка поставщиков остаётся доступной. При отсутствии
преимущества по average precision над SupplierAverageBaseline сигналы модели не выдаются.

По умолчанию файл и отчёт не архивируются. Для отдельного пилотного развёртывания на постоянном
диске клиента задайте `SITEPULSE_AUDIT_DIR=/data/sitepulse/audits`. Только явный запрос
`POST /audit/history?save=true` сохраняет нормализованный `deliveries.csv` и `report.json` в каталоге
с идентификатором сервера. Исходное имя файла не используется как путь. Настройте резервирование
и срок хранения этого диска в условиях пилота. Не включайте архивирование на публичном демо.
Пока роли Stage 6 не реализованы, аудит требует ключ администратора.
Для печати выберите A4 в альбомной ориентации и отключите колонтитулы браузера.
В Safari ориентацию нужно выбрать в диалоге печати вручную.

## 2. Health Monitoring & Endpoints

| Endpoint | Method | Expected Response | Description |
| :--- | :--- | :--- | :--- |
| `/health` | GET | `{"status": "ok", "engines": [...]}` | Heartbeat, active engines, trained row count. |
| `/metrics` | GET | Cross-validated scores, PR-AUC, lift | Model accuracy vs. baseline scorecard. |
| `/accuracy` | GET | `{"accuracy": 0.xx, "outcomes": n}` | Closed-loop verification of predictions vs. reality. |

### Health Check Alerting Rule
If `GET /health` returns non-200 or `x-process-time-ms > 500`:
1. Check process memory via `ps aux | grep uvicorn` or `docker stats`.
2. Inspect logs for uncaught exceptions in feature inference or OR-Tools solver.
3. If PostgreSQL is unresponsive, verify container connection string in `.env`.

---

## 3. Retraining & Model Management

The prediction engine is stateless and caches the model artifact in memory. When new delivery actuals arrive:

### Retrain Trigger
```bash
# Trigger hot-swapped retraining via API
curl -X POST http://127.0.0.1:8000/train

# Response:
# {"status": "retrained", "trained_rows": 2200, "metrics": {...}}
```
*Note: The API immediately clears its LRU cache and serves the new artifact with zero downtime.*

### CLI Manual Retraining
```bash
python3 -m ml.train data/synthetic/delay_prediction.csv
```

---

## 4. Incident Response & Troubleshooting

### Scenario A: Port Conflict (`Address already in use: 8000` or `8501`)
```bash
# Identify conflicting process
lsof -i :8000 -i :8501

# Terminate orphan process if necessary
kill -9 <PID>
```

### Scenario B: Cold-Start Supplier Warnings
* **Symptoms:** Supplier has no historical track record on a route.
* **Expected Behavior:** System automatically applies Bayesian shrinkage to material × route empirical priors.
* **Action:** No incident action required. Confirm `supplier_n_prior == 0` and `risk_band` reflects material priors rather than `NaN`.

### Scenario C: OR-Tools Solver Timeout
* **Symptoms:** `/schedule` latency exceeds 5 seconds.
* **Resolution:** Default time limit is 5.0 seconds. Check `booking_requests` dataset for cycle deadlocks or invalid time ranges ($T_{\text{end}} \le T_{\text{start}}$).
