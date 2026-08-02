

# AGENTE DE INVESTIGACIÓN FINANCIERA

<div align="center">

**Una canalización multiagente para investigación automatizada de futuros y revisión de informes**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![Stars](https://img.shields.io/github/stars/Adkid-Zephyr/Financial-research-agent-QBT?style=social)](https://github.com/Adkid-Zephyr/Financial-research-agent-QBT)

[English](#) | [中文](./README_CN.md) | [日本語](./README_JP.md)

---

*Construyendo un sistema automatizado de investigación de extremo a extremo para futuros de materias primas: desde la ingesta de datos hasta informes estructurados con garantía de calidad.*

</div>

---

## 🚀 LA HISTORIA

> **Por qué estoy construyendo esto en público**

En los flujos de trabajo tradicionales de investigación cuantitativa, los analistas dedican entre el 60 y el 70 % de su tiempo a tareas repetitivas: recopilar datos, dar formato a informes, hacer seguimiento de eventos y realizar controles de calidad iniciales. Este proyecto comenzó como un experimento para responder a una pregunta simple:

**¿Podemos construir un sistema que gestione el trabajo de la "canalización", para que los investigadores puedan centrarse en lo que realmente importa: el análisis y la toma de decisiones?**

Lo que comenzó como una prueba de concepto se ha convertido en un sistema completo de automatización de investigación con:
- Orquestación multiagente (LangGraph)
- Transmisión en tiempo real de eventos por WebSocket
- Backend FastAPI listo para producción
- Implementación con Docker Compose
- Revisión de calidad con rúbricas estructuradas

Este es un **proyecto de portafolio personal** desarrollado durante mi empleo en **AnnPoint (广州安点科技)**. La empresa amablemente me otorgó los derechos completos para publicar este proyecto de código abierto, manteniendo en privado las fuentes de datos propietarias.

---

## ✨ CARACTERÍSTICAS PRINCIPALES

| Característica | Descripción |
|---------|-------------|
| 🔀 **Canalización Multiagente** | Flujo de trabajo orquestado: Agregador → Analizador → Redactor → Revisor |
| 📊 **Fusión de Datos MultiFuente** | Instantáneas CTP, Yahoo Finance, datos de materias primas de AkShare |
| 🔄 **Bucle de Revisión** | Hasta 2 rondas de revisión de calidad con rúbricas estructuradas |
| 🌐 **FastAPI + WebSocket** | Transmisión en tiempo real de eventos para el monitoreo de tareas |
| 📦 **Almacenamiento PostgreSQL** | Archivo persistente de informes con API de consulta |
| 🐳 **Docker Compose** | Implementación con un solo comando: app + postgres + nginx |
| 🖥️ **Consola Web** | Verificación de estado, activación de tareas, transmisión de eventos, visor de informes |
| 📝 **Agente de Revisión de Informes** | Herramienta de revisión independiente con exportación a Markdown/PDF/JSON |

---

## 🏗️ ARQUITECTURA

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐ │
│  │ /runs   │  │/batches │  │/reports │  │ WebSocket /ws/events│ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Workflow                           │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │Aggregate │───▶│ Analyzer │───▶│  Writer  │───▶│ Reviewer │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │              │               │               │         │
│        ▼              ▼               ▼               ▼         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Data Source Registry                         │  │
│   │   CTP Snapshot │ Yahoo Finance │ AkShare │ Mock (dev)    │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│          PostgreSQL (production) / SQLite (local dev)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
.
├── futures_research/          # Flujo principal y API
│   ├── api/                   # Rutas FastAPI y frontend estático
│   ├── agents/                # Nodos LangGraph
│   ├── data_sources/          # Adaptadores CTP, Yahoo, AkShare
│   ├── storage/               # Repositorio PostgreSQL
│   └── events/                # Bus de eventos WebSocket
├── report_review_agent/       # Herramienta de revisión independiente
├── deploy/                    # Docker, Nginx, scripts cron
├── varieties/                 # Configuraciones YAML de commodities
├── tests/                     # 40+ pruebas unitarias
└── memory/                    # Documentación de transición de desarrollo
```

---

## ⚡ INICIO RÁPIDO

### Requisitos previos
- Python 3.11+
- Docker & Docker Compose (para implementación)

### Desarrollo local

```bash
# Clonar el repositorio
git clone https://github.com/Adkid-Zephyr/Financial-research-agent-QBT.git
cd Financial-research-agent-QBT

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar el servidor API
uvicorn futures_research.api.app:app --reload --port 8025
```

Luego abre:
- 🖥️ **Frontend**: http://127.0.0.1:8025/
- 🔧 **Consola de Admin**: http://127.0.0.1:8025/admin
- 📖 **Documentación de la API**: http://127.0.0.1:8025/docs
- 🔌 **WebSocket**: ws://127.0.0.1:8025/ws/events

### Implementación con Docker

```bash
# Copiar plantilla de entorno
cp .env.example .env

# Configurar ajustes (opcional: agregar ANTHROPIC_API_KEY para modo LLM)
# Editar .env con tu editor preferido

# Iniciar con Docker Compose
docker compose up --build -d

# Verificar estado
curl http://127.0.0.1:8080/healthz
```

Endpoints por defecto:
| Servicio | URL |
|---------|-----|
| Frontend | http://127.0.0.1:8080/ |
| Verificación de estado | http://127.0.0.1:8080/healthz |
| Documentación API | http://127.0.0.1:8080/docs |
| WebSocket | ws://127.0.0.1:8080/ws/events |

---

## 🔧 CONFIGURACIÓN

### Variables de Entorno

| Variable | Descripción | Valor predeterminado |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Clave API de LLM (opcional) | - |
| `ANTHROPIC_BASE_URL` | URL del punto de conexión LLM | - |
| `LLM_MODEL` | Identificador del modelo | `kimi-k2.5` |
| `DATABASE_URL` | DSN de PostgreSQL (opcional) | Fallback a SQLite |
| `ANALYSIS_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `REPORT_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `ENABLE_YAHOO_MARKET_SOURCE` | Habilitar datos de Yahoo Finance | `false` |
| `ENABLE_AKSHARE_COMMODITY_SOURCE` | Habilitar datos de AkShare | `false` |

### Ejecución con Fuentes de Datos Externas

```bash
ENABLE_YAHOO_MARKET_SOURCE=true \
ENABLE_AKSHARE_COMMODITY_SOURCE=true \
uvicorn futures_research.api.app:app --port 8025
```

---

## 📈 HOJA DE RUTA

> **Construyendo en público: hacia dónde vamos**

### Fase 2 (Planificada)
- [ ] Más integraciones de fuentes de datos (Wind, API de Bloomberg)
- [ ] Programación avanzada con orquestación de tareas
- [ ] Dimensiones de puntuación de informes más detalladas
- [ ] Frontend mejorado con reproducción histórica
- [ ] Soporte multiusuario con autenticación
- [ ] Pipeline CI/CD con GitHub Actions

### Estado Actual
- ✅ Fase 1 Completa: Flujo completo, API, WebSocket, Almacenamiento
- ✅ Implementación MVP con Docker Compose
- ✅ Fusión de datos multifuente (CTP + Yahoo + AkShare)
- ✅ Bucle de revisión de calidad con rúbricas estructuradas
- ✅ Consola web para monitoreo y control

---

## 🧪 PRUEBAS

```bash
# Ejecutar todas las pruebas
python -m unittest discover -s tests

# Ejecutar módulos específicos
python -m unittest tests.test_workflow tests.test_api

# Con cobertura (opcional)
pip install coverage
coverage run -m unittest discover -s tests
coverage report
```

---

## 📜 LICENCIA Y ATRIBUCIÓN

```
Copyright 2026 FENGSHUO LIU (刘丰硕)

Licensed under the Apache License, Version 2.0
```

Este proyecto fue desarrollado durante mi empleo en **AnnPoint 广州安点科技**. La empresa ha otorgado los derechos completos al autor para este proyecto personal de código abierto.

> ⚠️ **Nota**: Las fuentes de datos de nivel de tick proporcionadas por AnnPoint para pruebas siguen siendo propietarias y no se incluyen. Los usuarios pueden integrar sus propias fuentes de datos para pruebas y evaluación.

### Autor
**FENGSHUO LIU** ([@Adkid-Zephyr](https://github.com/Adkid-Zephyr))

### Agradecimientos
- **Kris77z** ([@Kris77z](https://github.com/Kris77z)) — Configuración del pipeline CI/CD y soporte de implementación
- **AnnPoint 广州安点科技** — Infraestructura de pruebas y soporte de fuentes de datos

---

## 🤝 CONTRIBUCIÓN

Este es un proyecto de portafolio personal, pero doy la bienvenida a:
- 🐛 Informes de errores y discusión de issues
- 💡 Sugerencias de características y comentarios sobre la hoja de ruta
- 📖 Mejoras en la documentación
- 🔀 Pull requests para correcciones de errores

¡Siéntete libre de abrir un issue o iniciar una discusión!

---

<div align="center">

**Construido con ❤️ por un cuant pasado a desarrollador que cree que la automatización de la investigación debe ser abierta y accesible.**

[⬆ Volver al Inicio](#financial-research-agent)

</div>
