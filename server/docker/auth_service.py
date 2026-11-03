import http.server, os, json, hashlib, hmac, threading, time, re
U="/ot/data/users.json"
SECRET=open("/ot/data/login_secret").read().strip().encode()   # shared with the UberDOG's login manager (otp/login/PlayToken.py)
TOKEN_SECONDS=24*3600   # long enough for the game's own reconnects after a phone sleeps
LOCK=threading.Lock()
FAILS={}   # key -> [timestamps] of failed recovery attempts
def load():
    try: return json.load(open(U))
    except Exception: return {"open_registration":True,"users":{}}
def save(db):
    json.dump(db,open(U+".tmp","w"),indent=1); os.replace(U+".tmp",U); os.chmod(U,0o666)
def pbk(text,salt): return hashlib.pbkdf2_hmac("sha256",text.encode(),bytes.fromhex(salt),100000).hex()
def norm(s): return " ".join(s.lower().split())
def play_token(name):
    signed="%s.%d"%(name,time.time()+TOKEN_SECONDS)
    return signed+"."+hmac.new(SECRET,signed.encode(),hashlib.sha256).hexdigest()
def check_name_pw(name,pw):
    if not (2<=len(name)<=20) or not name.replace("_","").replace("-","").isalnum(): return "Usernames are 2-20 letters, numbers, - or _."
    if len(pw)<4: return "Passwords need at least 4 characters."
    return None
def auth(text,new=False):
    """returns (error or None, user record or None). new: the player chose "I'm new", so an unknown name is registered"""
    if ":" not in text: return "Please enter a username and password.",None
    name,pw=text.split(":",1); name=name.strip().lower()
    e=check_name_pw(name,pw)
    if e: return e,None
    with LOCK:
        db=load(); u=db["users"].get(name)
        if u is None:
            if not new: return "No account called %s. New? Tap \"I'm new\"."%name,None
            if not db.get("open_registration",True): return "Unknown user. Ask a parent to add you.",None
            salt=os.urandom(16).hex(); u=db["users"][name]={"salt":salt,"hash":pbk(pw,salt),"dbkey":"user:"+name}
            save(db); return None,u
        if not hmac.compare_digest(u["hash"],pbk(pw,u["salt"])): return ("That name is taken. Pick another one." if new else "Wrong password."),None
        return None,u
def throttled(keys):
    now=time.time()
    for k in keys:
        FAILS[k]=[t for t in FAILS.get(k,[]) if now-t<3600]
        if len(FAILS[k])>=5: return True
    return False
def note_fail(keys):
    now=time.time()
    for k in keys: FAILS.setdefault(k,[]).append(now)
def set_recovery(text):
    parts=text.split("\n")
    if len(parts)<3: return "Fill in both boxes."
    err,u=auth(parts[0])
    if err or u is None: return err or "Sign in first."
    nick,toon=norm(parts[1]),norm(parts[2])
    if len(nick)<2 or len(toon)<2: return "Answers need at least 2 letters."
    name=parts[0].split(":",1)[0].strip().lower()
    with LOCK:
        db=load(); salt=os.urandom(16).hex()
        db["users"][name]["rec"]={"salt":salt,"nick":pbk(nick,salt),"toon":pbk(toon,salt)}
        save(db)
    return None
GENERIC="Those answers don't match. Ask a parent if you need help."
def recover(text,ip):
    parts=text.split("\n")
    if len(parts)<4: return "Fill in every box."
    name=parts[0].strip().lower(); nick,toon,newpw=norm(parts[1]),norm(parts[2]),parts[3]
    keys=("u:"+name,"ip:"+ip)
    if throttled(keys): return "Too many tries. Try again in an hour or ask a parent."
    e=check_name_pw(name,newpw)
    if e and e.startswith("Passwords"): return e
    with LOCK:
        db=load(); u=db["users"].get(name); rec=(u or {}).get("rec")
        ok=False
        if rec:
            a=hmac.compare_digest(rec["nick"],pbk(nick,rec["salt"]))
            b=hmac.compare_digest(rec["toon"],pbk(toon,rec["salt"]))
            ok=a and b
        else:
            pbk(nick,os.urandom(16).hex())  # keep timing similar
        if not ok:
            note_fail(keys); return GENERIC
        salt=os.urandom(16).hex(); u["salt"]=salt; u["hash"]=pbk(newpw,salt)
        save(db)
    FAILS.pop("u:"+name,None)
    return None
CLOG="/ot/data/logs/client.log"; CLOG_MAX=30*1024*1024; CLOG_RATE={}; CLOG_PER_HOUR=int(os.environ.get("CLOG_PER_HOUR","6000"))
def client_log(ip,text):
    now=time.time(); q=CLOG_RATE.setdefault(ip,[]); q[:]=[t for t in q if now-t<3600]
    if len(q)>=CLOG_PER_HOUR: return False
    try:
        if os.path.exists(CLOG) and os.path.getsize(CLOG)>CLOG_MAX: return False
        q.append(now)
        with LOCK, open(CLOG,"a",encoding="utf8") as f:
            line=text[:1500].replace(chr(10)," | ")
            f.write("%s %s %s%s"%(time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(now)),ip,line,chr(10)))
    except Exception: return False
    return True
DB="/ot/src/astron/databases"
SPECIES={"d":"dog","c":"cat","h":"horse","m":"mouse","r":"rabbit","f":"duck","p":"pig","b":"bear","s":"monkey"}
HEADS="dls dss dsl dll cls css csl cll hls hss hsl hll mls mss rls rss rsl rll fls fss fsl fll pls pss psl pll bls bss bsl bll sls sss ssl sll".split()
PLAYGROUNDS=[(2000,"Toontown Central"),(1000,"Donald's Dock"),(5000,"Daisy Gardens"),(4000,"Minnie's Melodyland"),(3000,"The Brrrgh"),(9000,"Donald's Dreamland")]
PLACES={**dict(PLAYGROUNDS),6000:"Chip 'n Dale's Acorn Acres",7000:"Funny Farm",8000:"Goofy Speedway",10000:"Bossbot HQ",11000:"Sellbot HQ",12000:"Cashbot HQ",
  13000:"Lawbot HQ",15000:"the Toontorial",16000:"their estate",17000:"Chip 'n Dale's MiniGolf",18000:"a party"}
BOARD={"at":0,"json":b""}
def db_fields(dbId):
    path="%s/astrondb/%d.yaml"%(DB,dbId); f={}
    for ln in open(path,encoding="utf8",errors="replace"):
        if ln.startswith("  ") and ": " in ln: k,v=ln.strip().split(": ",1); f[k]=v
    return f,os.path.getmtime(path)
def ints(v): return [int(n) for n in re.findall(r"-?\d+",v)]
def toon_entry(avId,username,playing,lastSeen):
    f,mtime=db_fields(avId)
    name=re.match(r'\("(.*)"\)$',f["setName"]).group(1).replace('\\"','"').replace("\\\\","\\")
    dna=f.get("setDNAString","")[2:-2]
    head=HEADS[int(dna[6:8],16)] if dna[4:6]=="74" else ""
    teleports=set(ints(f.get("setTeleportAccess","")))
    reached=[n for hood,n in PLAYGROUNDS if hood in teleports or hood==2000][-1]
    hood=ints(f.get("setLastHood","0"))[0]
    online=avId in playing
    return {"name":name,"username":username,"species":SPECIES.get(head[:1],""),"laff":ints(f["setMaxHp"])[0],"tracks":sum(ints(f.get("setTrackAccess",""))),
            "playground":reached,"online":online,
            "where":(PLACES.get(2000 if hood>=22000 else hood) if online else None),"lastSeen":int(lastSeen.get(str(avId),mtime))}
def leaderboard():
    """every toon on the server, best first: its laff, gag tracks and the furthest playground its Toontasks opened, and whether it is
    playing now (the UberDOG's online.json, see ToonPresenceUD) or when it last was"""
    now=time.time()
    if now-BOARD["at"]<10: return BOARD["json"]
    try: status=json.load(open("/ot/data/online.json"))
    except Exception: status={}
    playing=set(status.get("playing",[])) if now-status.get("updated",0)<120 else set()
    try: lastSeen=json.load(open("/ot/data/lastseen.json"))
    except Exception: lastSeen={}
    toons=[]
    try: accounts=json.load(open(DB+"/accounts.json")).items()
    except Exception: accounts=[]
    for username,accountId in accounts:
        try: avIds=ints(json.loads(db_fields(accountId)[0]["ACCOUNT_AV_SET"]))
        except Exception: continue
        for avId in avIds:
            if not avId: continue
            try: toons.append(toon_entry(avId,username,playing,lastSeen))
            except Exception as e: print("leaderboard: could not read toon",avId,repr(e),flush=True)
    order=[n for _,n in PLAYGROUNDS]
    toons.sort(key=lambda t:(-t["laff"],-t["tracks"],-order.index(t["playground"]),t["name"].lower()))
    BOARD.update(at=now,json=json.dumps({"now":int(now),"toons":toons}).encode())
    return BOARD["json"]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0]!="/leaderboard.json": return self.reply(404,"")
        body=leaderboard()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers()
        self.wfile.write(body)
    def reply(self,code,msg):
        self.send_response(code); self.end_headers(); self.wfile.write(msg.encode())
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0")); raw=self.rfile.read(n); body=raw.decode("utf-8","replace") if n<4096 else ""
        ip=self.headers.get("X-Forwarded-For") or self.client_address[0]
        if self.path=="/auth":
            err,u=auth(body,self.headers.get("X-Ttr-Mode")=="new")
            if err: return self.reply(403,err)
            name=body.split(":",1)[0].strip().lower()
            return self.reply(200,("ok " if u.get("rec") else "setup ")+play_token(name))
        if self.path=="/setrecovery":
            err=set_recovery(body); return self.reply(403 if err else 200,err or "ok")
        if self.path=="/recover":
            err=recover(body,ip); return self.reply(403 if err else 200,err or "ok")
        if self.path=="/__log":
            # a test session (page opened with ?log=1): keep what the game prints, with the time and the device's address
            return self.reply(204 if client_log(ip,body) else 429,"")
        self.reply(404,"")
    def log_message(self,*a): pass
http.server.ThreadingHTTPServer(("0.0.0.0",7381),H).serve_forever()
