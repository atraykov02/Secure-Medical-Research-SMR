# Secure Medical Research (SMR)

Уеб платформа за извършване на статистически анализи върху разпределени медицински данни чрез протокол за сигурни многостранни изчисления BGW. 

## Структура на проекта

```text
Secure-Medical-Research-SMR/
├── bgw/                         # BGW протокол, споделяне на дялове с Shamir и обмен на информация
├── coordinator/                 # Централен FastAPI координатор
├── hospital_node/               # FastAPI възел на медицинска организация
├── frontend/                    # Vue 3 и TypeScript интерфейс
├── experiments/                 # Експерименти с данните и резултати
├── tests/                       # Автоматизирани тестове
├── docker-compose.backend.yml   # Конфигурация на цялата система
├── requirements.txt             # Python зависимости
└── README.md                    # Ръководство за инсталация на проекта
```

## Изисквания

За инсталация и стартиране са необходими:

- Docker Desktop или Docker Engine;
- Docker Compose v2.

Не е необходимо Python, Node.js или PostgreSQL да бъдат инсталирани локално, когато проектът се стартира чрез Docker.

## Инсталация и стартиране с Docker

Клонирайте това repository и изпълнете командите:

```bash
git clone https://github.com/atraykov02/Secure-Medical-Research-SMR.git
cd Secure-Medical-Research-SMR
docker compose -f docker-compose.backend.yml up --build -d
```

При първото стартиране Docker изгражда необходимите образи, създава отделните PostgreSQL бази данни и зарежда демонстрационни данни. Състоянието на контейнерите се проверява с:

```bash
docker compose -f docker-compose.backend.yml ps
```

След успешно стартиране са достъпни:

- потребителски интерфейс: <http://localhost:5174>;
- Coordinator API: <http://localhost:8000>;

## Спиране на системата

```bash
docker compose -f docker-compose.backend.yml down
```

За премахване и на създадените бази данни:

```bash
docker compose -f docker-compose.backend.yml down -v
```

> Командата с `-v` изтрива Docker volumes и съхранените в тях демонстрационни данни.

## Локална среда за тестове и експерименти

Необходими са Python 3.12 или по-нова версия. В Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

В Linux или macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Стартиране на автоматизираните тестове:

```bash
python -m pytest -q
```

Стартиране на експериментите с данните:

```bash
python -m experiments.run_benchmarks
```

Резултатите се записват като JSON и CSV файлове в папка `experiments/results/`.

## Локално стартиране на frontend частта

Необходими са Node.js 22 и npm. Координатор API трябва да работи на `http://localhost:8000`.

```bash
cd frontend
npm ci
npm run dev
```

## Начално генерирани акаунти за достъп до системата

Данните за вход са приложени към дипломната работа.
