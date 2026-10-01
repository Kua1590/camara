
import os, time, uuid, threading
from flask import Flask, request, jsonify, Response, make_response

app = Flask(__name__)

TOKEN = os.environ.get("DIGITAL_IRIS_TOKEN", "")
if not TOKEN:
    print("ADVERTENCIA: define DIGITAL_IRIS_TOKEN en el servidor.")

lock = threading.Lock()
homes = {}

def auth():
    bearer = request.headers.get("Authorization","")
    token = bearer[7:] if bearer.startswith("Bearer ") else ""
    return TOKEN and token == TOKEN

def home_id():
    return request.headers.get("X-Home-ID","casa").strip() or "casa"

def get_home(hid):
    with lock:
        h = homes.setdefault(hid,{
            "frame":None,
            "frame_ts":0.0,
            "status":{"online":False},
            "events":[],
            "commands":[],
            "results":{}
        })
        return h

@app.post("/agent/frame")
def agent_frame():
    if not auth(): return "unauthorized",401
    hid=home_id(); h=get_home(hid)
    data=request.get_data()
    if not data: return "empty",400
    with lock:
        h["frame"]=data
        h["frame_ts"]=time.time()
    return "ok"

@app.post("/agent/status")
def agent_status():
    if not auth(): return "unauthorized",401
    hid=home_id(); h=get_home(hid)
    with lock:
        h["status"]=request.get_json(silent=True) or {}
        h["status"]["relay_last_seen"]=time.time()
    return "ok"

@app.post("/agent/events")
def agent_events():
    if not auth(): return "unauthorized",401
    hid=home_id(); h=get_home(hid)
    payload=request.get_json(silent=True) or {}
    with lock:
        h["events"]=(payload.get("events") or [])[:100]
    return "ok"

@app.get("/agent/commands")
def agent_commands():
    if not auth(): return jsonify({"commands":[]}),401
    hid=home_id(); h=get_home(hid)
    with lock:
        cmds=h["commands"][:]
        h["commands"].clear()
    return jsonify({"commands":cmds})

@app.post("/agent/command_result")
def agent_command_result():
    if not auth(): return "unauthorized",401
    hid=home_id(); h=get_home(hid)
    payload=request.get_json(silent=True) or {}
    cid=str(payload.get("id",""))
    with lock:
        h["results"][cid]={"answer":payload.get("answer",""),"ts":time.time()}
    return "ok"

HTML = """<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Digital Iris</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,Arial;background:#090b0f;color:#eef2f7;margin:0}
header{position:sticky;top:0;background:#0f131a;padding:14px 16px;border-bottom:1px solid #222}
main{padding:12px;max-width:900px;margin:auto}
.card{background:#12161d;border:1px solid #232a35;border-radius:16px;margin-bottom:12px;overflow:hidden}
.pad{padding:14px}.live{width:100%;display:block;background:#000;min-height:220px;object-fit:contain}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pill{background:#1d2430;padding:10px;border-radius:12px;font-size:13px}
textarea,input{width:100%;box-sizing:border-box;background:#0b0e13;color:white;border:1px solid #333;border-radius:12px;padding:12px;font-size:16px}
button{margin-top:8px;background:#fff;color:#111;border:0;border-radius:12px;padding:12px 16px;font-weight:700}
.event{padding:9px 0;border-bottom:1px solid #222;font-size:13px}
</style></head><body>
<header><b>Digital Iris</b><div id="s" style="font-size:12px;color:#98a2b3">conectando…</div></header>
<main>
<div class="card"><img class="live" id="cam"></div>
<div class="grid"><div class="pill" id="net">Red…</div><div class="pill" id="ai">IA…</div></div>
<div class="card pad" style="margin-top:12px"><b>Preguntar a la memoria</b>
<textarea id="q" rows="2" placeholder="¿Qué pasó hoy?"></textarea>
<button onclick="ask()">Buscar</button><div id="ans" style="white-space:pre-wrap;margin-top:10px"></div></div>
<div class="card pad"><b>Últimos eventos</b><div id="events"></div></div>
</main>
<script>
const u=new URL(location.href); const home=u.searchParams.get('home')||'casa';
function img(){document.getElementById('cam').src='/frame?home='+encodeURIComponent(home)+'&t='+Date.now()}
async function refresh(){
 try{
  const st=await (await fetch('/api/status?home='+encodeURIComponent(home))).json();
  document.getElementById('s').textContent=st.online?'CASA EN LÍNEA':'sin conexión reciente';
  document.getElementById('net').textContent='Red: '+(st.wifi||'-');
  document.getElementById('ai').textContent='IA: '+(st.ai||'-');
  const ev=await (await fetch('/api/events?home='+encodeURIComponent(home))).json();
  document.getElementById('events').innerHTML=ev.map(x=>'<div class="event"><b>'+x.ts+'</b> · '+x.description+'</div>').join('');
 }catch(e){}
}
async function ask(){
 const q=document.getElementById('q').value;
 document.getElementById('ans').textContent='Consultando la laptop…';
 const r=await fetch('/api/query?home='+encodeURIComponent(home),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})});
 const j=await r.json();document.getElementById('ans').textContent=j.answer||'Sin respuesta';
}
setInterval(img,350); setInterval(refresh,2500); img(); refresh();
</script></body></html>"""

@app.get("/")
def index():
    return Response(HTML,mimetype="text/html")

@app.get("/frame")
def frame():
    hid=request.args.get("home","casa"); h=get_home(hid)
    with lock:
        data=h["frame"]
    if not data: return Response(status=204)
    resp=make_response(data)
    resp.headers["Content-Type"]="image/jpeg"
    resp.headers["Cache-Control"]="no-store"
    return resp

@app.get("/api/status")
def api_status():
    hid=request.args.get("home","casa"); h=get_home(hid)
    with lock:
        st=dict(h["status"])
        fresh=time.time()-h["frame_ts"]<8
    st["online"]=bool(fresh)
    return jsonify(st)

@app.get("/api/events")
def api_events():
    hid=request.args.get("home","casa"); h=get_home(hid)
    with lock:
        return jsonify(h["events"])

@app.post("/api/query")
def api_query():
    hid=request.args.get("home","casa"); h=get_home(hid)
    payload=request.get_json(silent=True) or {}
    q=payload.get("q","").strip()
    if not q: return jsonify({"answer":"Escribe una pregunta."})
    cid=str(uuid.uuid4())
    with lock:
        h["commands"].append({"id":cid,"q":q})
    end=time.time()+12
    while time.time()<end:
        with lock:
            result=h["results"].pop(cid,None)
        if result:
            return jsonify({"answer":result["answer"]})
        time.sleep(0.25)
    return jsonify({"answer":"La laptop no respondió a tiempo. Verifica que Digital Iris Relay esté activo."})

if __name__=="__main__":
    port=int(os.environ.get("PORT","8080"))
    app.run(host="0.0.0.0",port=port,threaded=True)
