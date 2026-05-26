#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta, timezone
import random
import os
import base64

# Configuración
JIRA_URL = "https://procontacto.atlassian.net"
EMAIL = "axel.colamarino@procontacto.com.mx"
API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Tareas
TASKS = [
    {"key": "CYDP-294", "hours": 5},
    {"key": "RI-12", "hours": 1},
    {"key": "CMIV2-194", "hours": None},  # Random entre 2 y 4
]

def get_business_days(start_date, end_date):
    """Retorna lista de días hábiles (lunes-viernes) en el rango"""
    business_days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 0-4 son lunes a viernes
            business_days.append(current)
        current += timedelta(days=1)
    return business_days

def add_worklog(task_key, date, hours, max_retries=3):
    """Agrega un worklog a una tarea con reintentos en caso de error"""
    url = f"{JIRA_URL}/rest/api/3/issue/{task_key}/worklog"

    # Convertir horas a segundos
    time_spent_seconds = int(hours * 3600)

    started_str = date.strftime("%Y-%m-%dT09:00:00.000+0000")

    payload = {
        "timeSpentSeconds": time_spent_seconds,
        "started": started_str
    }

    auth_string = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code in [201, 200]:
                print(f"✓ {task_key}: {hours}h agregadas para {date.strftime('%Y-%m-%d')}")
                return True
            else:
                print(f"✗ {task_key}: Error {response.status_code} - {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠ {task_key}: Reintentando en {wait_time}s ({attempt + 1}/{max_retries})...")
                import time
                time.sleep(wait_time)
            else:
                print(f"✗ {task_key}: Error de conexión después de {max_retries} intentos - {str(e)}")
                return False

def main():
    # Calcular rango de fechas (1 al 15 de mayo de 2026)
    start_date = datetime(2026, 5, 1)
    end_date = datetime(2026, 5, 15)

    business_days = get_business_days(start_date, end_date)

    print(f"Días hábiles encontrados: {len(business_days)}")
    for day in business_days:
        print(f"  - {day.strftime('%A, %Y-%m-%d')}")
    print()

    # Agregar worklogs
    total_creados = 0
    for task in TASKS:
        task_key = task["key"]
        hours = task["hours"]

        print(f"\nAgregando worklogs para {task_key}...")

        for day in business_days:
            if hours is None:
                # Random entre 2 y 4 horas
                actual_hours = random.uniform(2, 4)
                actual_hours = round(actual_hours, 2)
            else:
                actual_hours = hours

            if add_worklog(task_key, day, actual_hours):
                total_creados += 1

    print(f"\n✓ Total de worklogs creados: {total_creados}")

if __name__ == "__main__":
    main()
