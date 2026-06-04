# Herramientas por Evaluar

Listado de herramientas y mejoras candidatas para incorporar al agente de QA.
Se irán evaluando e implementando de a una.

---

## 1. `ant` — Anthropic CLI

**Fuente:** [@ClaudeDevs, 2 jun 2026](https://x.com/ClaudeDevs/status/2061877343078244459)

**¿Qué es?**
CLI oficial de Anthropic para interactuar con la plataforma Claude desde la terminal y desde CI/CD.

**Capacidades relevantes para el agente:**

| Capacidad | Comando | Utilidad |
|---|---|---|
| Versionar el agente como YAML en Git | `ant beta:agents update` | Reemplaza el push manual del `.md` al repo |
| Sincronizar desde CI | `ant beta:agents update` en GitHub Actions | Cada push al repo actualiza el agente en la plataforma automáticamente |
| Ver trazas completas de ejecución | `ant beta:agents sessions get` | Más detalle que los logs actuales de BQ — muestra cada tool call y decisión |
| Auth unificada | `ant auth login` | Un solo token OAuth para CLI + SDK |
| Ejecutar sesiones de agente desde terminal | `ant beta:agents sessions create` | Útil para testing manual del agente sin disparar el webhook |

**Estado:** Por evaluar
**Instalación:** `brew install ant` / `curl` / `go`
