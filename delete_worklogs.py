#!/usr/bin/env python3
import requests
import os
import base64
from datetime import datetime, timedelta, timezone

# Configuración
JIRA_URL = "https://procontacto.atlassian.net"
EMAIL = "axel.colamarino@procontacto.com.mx"
API_TOKEN = os.getenv("JIRA_API_TOKEN")

TASKS = ["CYDP-294", "RI-12", "CMIV2-194"]

def get_worklogs(task_key):
    """Obtiene todos los worklogs de una tarea"""
    url = f"{JIRA_URL}/rest/api/3/issue/{task_key}/worklog"

    auth_string = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json().get('worklogs', [])
    else:
        print(f"Error obteniendo worklogs de {task_key}: {response.status_code}")
        return []

def delete_worklog(task_key, worklog_id):
    """Elimina un worklog específico"""
    url = f"{JIRA_URL}/rest/api/3/issue/{task_key}/worklog/{worklog_id}"

    auth_string = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_string}",
    }

    response = requests.delete(url, headers=headers)

    if response.status_code in [204, 200]:
        return True
    else:
        print(f"Error eliminando worklog {worklog_id} de {task_key}: {response.status_code}")
        return False

def main():
    start_date = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 5, 15, 23, 59, 59, tzinfo=timezone.utc)

    total_deleted = 0

    for task_key in TASKS:
        print(f"\nObteniendo worklogs de {task_key}...")
        worklogs = get_worklogs(task_key)

        # Filtrar worklogs en el rango de fechas especificado
        worklogs_to_delete = []
        for wl in worklogs:
            started = datetime.fromisoformat(wl['started'].replace('Z', '+00:00'))
            if start_date <= started <= end_date:
                worklogs_to_delete.append(wl)

        print(f"Encontrados {len(worklogs_to_delete)} worklogs para eliminar en {task_key}")

        for wl in worklogs_to_delete:
            started = wl['started']
            worklog_id = wl['id']
            if delete_worklog(task_key, worklog_id):
                print(f"✓ {task_key}: Eliminado worklog de {started}")
                total_deleted += 1
            else:
                print(f"✗ {task_key}: Error al eliminar worklog {worklog_id}")

    print(f"\n✓ Total de worklogs eliminados: {total_deleted}")

if __name__ == "__main__":
    main()
