# Proxy — exécute live_kalman.py depuis la racine du projet
# Streamlit lance chaque page depuis la racine, donc le chemin est stable.
exec(open("live_kalman.py", encoding="utf-8").read())
