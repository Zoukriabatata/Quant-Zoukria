@echo off
title Quant Maths - Apprentissage
cd /d "%~dp0"
streamlit run app_learning.py --server.port 8501
pause
