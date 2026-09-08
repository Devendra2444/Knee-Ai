# KneeAI

## Project
KneeAI is a clinical decision-support prototype for knee MRI review. It is designed for ideation demonstrations, not autonomous diagnosis.

## Problem
Radiologists reviewing knee MRI studies must triage many studies and focus attention on potentially important findings. The workflow is time-sensitive and benefits from a system that highlights likely abnormal findings and supports prioritization.

## Solution
KneeAI provides a complete prototype workflow: upload MRI study images, preprocess them, run a demo AI inference pipeline, generate explainability overlays, calculate a prototype triage score, and create an AI-assisted report for clinician review.

## Architecture
Frontend
↓
FastAPI
↓
ML Service
↓
MongoDB

## Setup
### Frontend
npm install
npm run dev

### Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

## Environment Variables
Use .env.example as a template and create a local .env file with the project settings.

## Model
A real model checkpoint can later be placed in the project and wired through the RealInferenceProvider abstraction. The default backend uses the clearly labeled PrototypeInferenceProvider.

## Demo Mode
The prototype runs in Demonstration / Prototype Mode by default so the workflow can be demonstrated even without a trained model or external infrastructure.

## Medical Disclaimer
KneeAI is a research prototype for clinical decision support. AI-generated predictions are not a diagnosis and must be reviewed by a qualified medical professional.
