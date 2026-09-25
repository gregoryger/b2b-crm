"""Ролевая модель.

Менеджер работает только со своими клиентами, лидами, сделками и задачами.
Руководитель видит все данные отдела продаж и аналитику.
Маркетолог работает с лидами, источниками, сегментами и выгрузками, сделки видит только в агрегированной аналитике.
Администратор настраивает систему: пользователи, справочники, поля, интеграции, аудит.
"""
from enum import Enum


class Role(str, Enum):
    admin = "admin"
    head = "head"
    manager = "manager"
    marketer = "marketer"


ROLE_LABELS = {
    Role.admin: "Администратор",
    Role.head: "Руководитель",
    Role.manager: "Менеджер",
    Role.marketer: "Маркетолог",
}

A, H, M, K = Role.admin, Role.head, Role.manager, Role.marketer

PERMISSIONS: dict[str, set[Role]] = {
    # Видимость данных без ограничения «только свои»
    "companies.view_all": {A, H, K},
    "leads.view_all": {A, H, K},
    "deals.view_all": {A, H},
    "tasks.view_all": {A, H},
    # Действия
    "companies.edit": {A, H, M},
    "companies.delete": {A, H},
    "companies.reassign": {A, H},
    "leads.edit": {A, H, M, K},
    "leads.delete": {A, H},
    "deals.view": {A, H, M},
    "deals.edit": {A, H, M},
    "deals.delete": {A, H},
    "tasks.edit": {A, H, M, K},
    "proposals.edit": {A, H, M},
    "finance.view": {A, H, M},
    "finance.edit": {A, H, M},
    "analytics.view": {A, H, M, K},
    "analytics.team": {A, H, K},
    "marketing.edit": {A, H, K},
    "import": {A, H, K},
    "export": {A, H, K},
    "products.edit": {A, H},
    "dictionaries.edit": {A},
    "pipeline.edit": {A, H},
    "templates.edit": {A, H},
    "custom_fields.edit": {A},
    "users.manage": {A},
    "settings.manage": {A},
    "audit.view": {A, H},
    "integrations.manage": {A},
}


def has_perm(role: str | Role, perm: str) -> bool:
    return Role(role) in PERMISSIONS.get(perm, set())


def permissions_for(role: str | Role) -> list[str]:
    r = Role(role)
    return sorted(p for p, roles in PERMISSIONS.items() if r in roles)
