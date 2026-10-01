DIGITAL IRIS RELAY - RENDER

1. Sube estos archivos a un repositorio de GitHub.
2. En Render: New > Web Service.
3. Conecta el repositorio.
4. Build Command:
   pip install -r requirements.txt
5. Start Command:
   gunicorn -w 1 -b 0.0.0.0:$PORT relay_server:app
6. En Environment agrega:
   DIGITAL_IRIS_TOKEN = el mismo token secreto que aparece en Digital Iris.
7. Crea el servicio.
8. Render te dará una URL parecida a:
   https://digital-iris-relay.onrender.com
9. Copia ESA URL en:
   Digital Iris > Remoto / iPhone > URL del relay
10. Pulsa Iniciar Relay.

No agregues / al final.
No abras los puertos del DVR.
