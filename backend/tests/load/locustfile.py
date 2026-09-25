"""Нагрузочный тест (п. 8.2 ТЗ): 50 одновременных пользователей, списки ~1000 записей, отклик < 2 сек.

Запуск (из контейнера backend или локально с установленным locust):
    locust -f tests/load/locustfile.py --host http://localhost:8080 --users 50 --spawn-rate 5 \
           --run-time 5m --headless --csv load_report

Перед запуском увеличьте лимит запросов для теста (RATE_LIMIT_PER_MINUTE) либо используйте разные учётные записи:
все демо-пользователи имеют пароль demo12345.
"""
import random

from locust import HttpUser, between, task

USERS = ["petrov@demo.ru", "kozlova@demo.ru", "nikitin@demo.ru", "orlova@demo.ru", "head@demo.ru", "marketer@demo.ru"]


class CrmUser(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        email = random.choice(USERS)
        r = self.client.post("/api/v1/auth/login", json={"email": email, "password": "demo12345"}, name="login")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        self.is_marketer = email.startswith("marketer")

    @task(5)
    def dashboard(self):
        self.client.get("/api/v1/analytics/dashboard", name="dashboard")

    @task(6)
    def companies(self):
        self.client.get("/api/v1/companies", params={"page_size": 100, "sort": "-revenue"}, name="companies list")

    @task(4)
    def search(self):
        self.client.get("/api/v1/search", params={"q": random.choice(["Сиб", "ООО", "Тех", "Петров", "77"])},
                        name="global search")

    @task(4)
    def leads(self):
        self.client.get("/api/v1/leads", params={"page_size": 100}, name="leads list")

    @task(4)
    def board(self):
        if not self.is_marketer:
            self.client.get("/api/v1/deals/board", name="deals board")

    @task(3)
    def my_tasks(self):
        self.client.get("/api/v1/tasks", params={"scope": "mine", "status": "open"}, name="tasks")

    @task(2)
    def report(self):
        self.client.get("/api/v1/analytics/reports/managers", name="report managers")

    @task(2)
    def company_card(self):
        r = self.client.get("/api/v1/companies", params={"page_size": 20}, name="companies list")
        items = r.json().get("items") or []
        if items:
            cid = random.choice(items)["id"]
            self.client.get(f"/api/v1/companies/{cid}", name="company card")
            self.client.get("/api/v1/activities", params={"company_id": cid}, name="timeline")
