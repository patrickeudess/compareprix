"""Point d'entrée WSGI (PythonAnywhere, mod_wsgi, uWSGI...) : `from wsgi import application`.

L'application utilise des chemins relatifs (data/, templates/) : on se place d'abord dans le dossier du projet,
car certains hébergeurs démarrent le processus ailleurs. Variables d'environnement à définir chez l'hébergeur :
COMPAREPRIX_ADMIN_TOKEN (obligatoire pour /admin), COMPAREPRIX_TRUSTED_PROXIES, COMPAREPRIX_HSTS.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)


from app import app as application  # noqa: E402, F401  (ré-exportation : c'est l'objet que l'hébergeur charge)
