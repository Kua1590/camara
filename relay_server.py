
import os,time,uuid,threading
from flask import Flask,request,jsonify,Response,make_response,stream_with_context

app=Flask(__name__)
TOKEN=os.environ.get("DIGITAL_IRIS_TOKEN","")
lock=threading.Condition()
homes={}

def auth():
    h=request.headers.get("Authorization","")
    return bool(TOKEN) and h=="Bearer "+TOKEN

def hid():
    return request.headers.get("X-Home-ID","casa").strip() or "casa"

def home(k):
    with lock:
        return homes.setdefault(k,{"frame":None,"seq":0,"frame_ts":0.0,"status":{},"events":[],"commands":[],"results":{}})

@app.post("/agent/frame")
def agent_frame():
    if not auth():return "unauthorized",401
    h=home(hid()); data=request.get_data()
    with lock:
        h["frame"]=data; h["frame_ts"]=time.time(); h["seq"]+=1; lock.notify_all()
    return "ok"

@app.post("/agent/status")
def agent_status():
    if not auth():return "unauthorized",401
    h=home(hid())
    with lock:
        h["status"]=request.get_json(silent=True) or {}; h["status"]["last_seen"]=time.time()
    return "ok"

@app.post("/agent/events")
def agent_events():
    if not auth():return "unauthorized",401
    h=home(hid()); p=request.get_json(silent=True) or {}
    with lock:h["events"]=(p.get("events") or [])[:100]
    return "ok"

@app.get("/agent/commands")
def commands():
    if not auth():return jsonify({"commands":[]}),401
    h=home(hid())
    with lock:
        c=h["commands"][:];h["commands"].clear()
    return jsonify({"commands":c})

@app.post("/agent/command_result")
def command_result():
    if not auth():return "unauthorized",401
    h=home(hid());p=request.get_json(silent=True) or {}
    with lock:h["results"][str(p.get("id"))]=p.get("answer","")
    return "ok"

HTML="""<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Digital Iris</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,Arial;background:#090b0f;color:#f3f5f7;margin:0}
header{padding:16px;position:sticky;top:0;background:#0f131a;border-bottom:1px solid #252b34}
main{padding:12px;max-width:900px;margin:auto}.card{background:#12161d;border:1px solid #252b34;border-radius:18px;margin-bottom:12px;overflow:hidden}
.cam{width:100%;display:block;background:#000;min-height:220px;object-fit:contain}.pad{padding:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.pill{background:#1d2430;padding:12px;border-radius:12px}
textarea{width:100%;box-sizing:border-box;background:#0b0e13;color:#fff;border:1px solid #333;border-radius:12px;padding:12px;font-size:16px}
button{padding:12px 18px;border:0;border-radius:12px;margin-top:8px;font-weight:700}.event{padding:9px 0;border-bottom:1px solid #222;font-size:13px}
</style></head><body>
<header><b style="font-size:22px">Digital Iris</b><div id=s>conectando…</div></header>
<main>
<div class=card><img class=cam id=cam></div>
<div class=grid><div class=pill id=net>Red: -</div><div class=pill id=ai>IA: -</div></div>
<div class="card pad"><b>Preguntar a la memoria</b><textarea id=q rows=2 placeholder="¿Qué pasó hoy?"></textarea><button onclick=ask()>Buscar</button><div id=ans></div></div>
<div class="card pad"><b>Últimos eventos</b><div id=events></div></div>
</main><script>
const u=new URL(location.href),home=u.searchParams.get('home')||'casa';
document.getElementById('cam').src='/stream?home='+encodeURIComponent(home);
async function refresh(){try{
 let st=await (await fetch('/api/status?home='+encodeURIComponent(home))).json();
 document.getElementById('s').textContent=st.online?'CASA EN LÍNEA':'sin conexión reciente';
 document.getElementById('net').textContent='Red: '+(st.wifi||'-');
 document.getElementById('ai').textContent='IA: '+(st.ai||'-');
 let ev=await (await fetch('/api/events?home='+encodeURIComponent(home))).json();
 document.getElementById('events').innerHTML=ev.map(x=>'<div class=event><b>'+x.ts+'</b> · '+x.description+'</div>').join('');
}catch(e){}}
async function ask(){let q=document.getElementById('q').value;document.getElementById('ans').textContent='Consultando…';
let r=await fetch('/api/query?home='+encodeURIComponent(home),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})});
let j=await r.json();document.getElementById('ans').textContent=j.answer||'';}
setInterval(refresh,2500);refresh();
</script></body></html>"""

@app.get("/")
def index():return Response(HTML,mimetype="text/html")

@app.get("/stream")
def stream():
    k=request.args.get("home","casa");h=home(k)
    def gen():
        last=-1
        while True:
            with lock:
                lock.wait_for(lambda:h["seq"]!=last,timeout=15)
                if h["seq"]==last: continue
                last=h["seq"];data=h["frame"]
            if data:
                yield b"--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n"+data+b"\r\n"
    return Response(stream_with_context(gen()),mimetype="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/status")
def status():
    h=home(request.args.get("home","casa"))
    with lock:
        st=dict(h["status"]);st["online"]=time.time()-h["frame_ts"]<8
    return jsonify(st)

@app.get("/api/events")
def events():
    h=home(request.args.get("home","casa"))
    with lock:return jsonify(h["events"])

@app.post("/api/query")
def query():
    h=home(request.args.get("home","casa"));p=request.get_json(silent=True) or {};q=p.get("q","").strip()
    if not q:return jsonify({"answer":"Escribe una pregunta."})
    cid=str(uuid.uuid4())
    with lock:h["commands"].append({"id":cid,"q":q})
    end=time.time()+12
    while time.time()<end:
        with lock:
            if cid in h["results"]:return jsonify({"answer":h["results"].pop(cid)})
        time.sleep(.2)
    return jsonify({"answer":"La laptop no respondió a tiempo."})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")),threaded=True)
