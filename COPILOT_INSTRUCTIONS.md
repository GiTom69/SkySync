# Copilot Instructions for SkySync 2.0

This document provides the necessary context and instructions for GitHub Copilot to assist with the SkySync 2.0 project.

## Project Overview
SkySync is a smart, automated flight-tracking application (desktop and web) that integrates with stable flight data APIs such as Amadeus for Developers and Duffel. It aggregates pricing data across airlines, provides AI-powered buy/wait recommendations, and alerts users when fares hit target thresholds.

## Target Audience
Budget-conscious travelers, digital nomads, and frequent flyers who want to optimize travel spending without manually searching or refreshing multiple websites.

## Key Features
- Multi-source flight-price aggregation via official APIs (Amadeus, Duffel)
- Customizable search windows and permutation of dates
- Baggage and fare class filtering including basic-economy exclusion
- Split-direction price history and split-ticketing engine
- Scheduled periodic scans using APScheduler
- Time-series forecasting (Prophet/ARIMA) for buy/wait signals
- Smart threshold alerts with desktop notifications and email
- Clean GUI: either a Python desktop frontend (PyQt6/customtkinter) or a FastAPI web UI with Chart.js

## Tech Stack
- Python 3.11+, Amadeus SDK, Duffel API, requests/httpx
- APScheduler for scheduling
- SQLite/SQLAlchemy for local data storage
- pandas, numpy, Prophet, scikit-learn for analytics
- plyer for notifications, smtplib for email
- GUI via PyQt6/customtkinter or FastAPI + Jinja2
- Poetry for dependency management, dotenv for config
- PyInstaller or Docker for packaging

## Development Guidelines
- Use Python 3.11+ and maintain type hints where feasible
- Follow PEP 8 style and maintain modular design
- Write tests for API integration, scheduling logic, forecasting
- Keep API keys out of source control; use `.env` for configuration

## Copilot Usage Suggestions
- When implementing new features, refer back to this file for context
- Suggest code snippets for API interactions, database models, and scheduler jobs
- Provide help with PyQt6 or FastAPI frontends based on chosen path
- Assist with packaging scripts (PyInstaller spec, Dockerfiles)

---

Use this instruction file to keep Copilot aligned with the objectives and architecture of the SkySync project.