"""Local community help board. Uses only Python's standard library."""
from __future__ import annotations
import json, os, sqlite3, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DB_PATH = Path(os.environ.get('COMMUNITY_DB', Path(__file__).with_name('community.db')))
KINDS = {'help', 'offer'}
STATUSES = {'open', 'coordinating', 'resolved'}


from contextlib import contextmanager
@contextmanager
def connect(path=DB_PATH):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path=DB_PATH):
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('help','offer')),
            title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL,
            area TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL)''')
        count = db.execute('SELECT count(*) FROM posts').fetchone()[0]
        if count == 0:
            demo = [
                ('help','Ride to the Saturday food pantry','Looking for a lift to collect a pantry box.','Transport','Northside'),
                ('offer','Garden tools for a weekend','Can lend basic hand tools for a neighborhood planting day.','Supplies','Northside'),
                ('help','Help carrying donated books','A few boxes need moving from the library foyer.','Moving','Riverside'),
                ('offer','One hour of math practice','Happy to help a neighbor review middle-school fractions.','Learning','Riverside')]
            db.executemany('INSERT INTO posts(kind,title,description,category,area,status,created_at) VALUES(?,?,?,?,?,\'open\',?)', [r + (datetime.now(timezone.utc).isoformat(),) for r in demo])


def create_post(data, path=DB_PATH):
    kind = str(data.get('kind', '')).strip().lower()
    fields = {key: str(data.get(key, '')).strip() for key in ('title','description','category','area')}
    if kind not in KINDS: raise ValueError('Choose a help request or volunteer offer.')
    if any(not v for v in fields.values()): raise ValueError('All fields are required.')
    if any(len(v) > 500 for v in fields.values()): raise ValueError('Each field must be 500 characters or fewer.')
    with connect(path) as db:
        cur = db.execute('INSERT INTO posts(kind,title,description,category,area,status,created_at) VALUES(?,?,?,?,?,\'open\',?)', (kind, fields['title'], fields['description'], fields['category'], fields['area'], datetime.now(timezone.utc).isoformat()))
        return dict(db.execute('SELECT * FROM posts WHERE id=?', (cur.lastrowid,)).fetchone())


def list_posts(path=DB_PATH):
    with connect(path) as db: return [dict(r) for r in db.execute('SELECT * FROM posts ORDER BY id DESC')]


def find_matches(post_id, path=DB_PATH):
    with connect(path) as db:
        post = db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
        if post is None: raise KeyError('Post not found.')
        opposite = 'offer' if post['kind'] == 'help' else 'help'
        rows = db.execute("SELECT * FROM posts WHERE kind=? AND status='open' AND id<>? AND (lower(category)=lower(?) OR lower(area)=lower(?)) ORDER BY CASE WHEN lower(category)=lower(?) THEN 0 ELSE 1 END, id DESC", (opposite, post_id, post['category'], post['area'], post['category']))
        return [dict(r) for r in rows]


def set_status(post_id, status, path=DB_PATH):
    if status not in STATUSES: raise ValueError('Status must be open, coordinating, or resolved.')
    with connect(path) as db:
        cur = db.execute('UPDATE posts SET status=? WHERE id=?', (status, post_id))
        if cur.rowcount == 0: raise KeyError('Post not found.')
        return dict(db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone())

PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Neighborly · Community help</title><style>
:root{font:16px/1.5 system-ui;color:#19352d;background:#f4f7f2}*{box-sizing:border-box}body{margin:0}.hero{padding:3.5rem max(6vw,24px);background:linear-gradient(120deg,#164e3b,#2f8060);color:white}.hero h1{font-size:clamp(2.2rem,5vw,4rem);line-height:1.05;max-width:700px;margin:.5rem 0}.hero p{max-width:660px;color:#e1f1e9}.wrap{max-width:1120px;margin:2rem auto;padding:0 22px}.layout{display:grid;grid-template-columns:340px 1fr;gap:24px}.panel,.card{background:white;border:1px solid #e2e9e3;border-radius:18px;padding:22px;box-shadow:0 8px 26px #1c48350b}.panel{align-self:start}.card{margin-bottom:12px}.card h3{margin:.25rem 0}.tag{font-size:.77rem;background:#e8f4ed;color:#246548;padding:4px 10px;border-radius:999px}.meta{color:#667a70;font-size:.88rem}.btn,button{border:0;border-radius:10px;background:#216b4c;color:white;padding:10px 14px;font:inherit;cursor:pointer}.btn.secondary{background:#eaf3ed;color:#1d5e43}input,textarea,select{width:100%;border:1px solid #cad8ce;border-radius:10px;padding:11px;margin:5px 0 12px;font:inherit;background:white}label{font-size:.9rem;font-weight:650}.toolbar{display:flex;justify-content:space-between;gap:10px;align-items:center;margin:0 0 12px}.empty{padding:28px;text-align:center;color:#718178}.note{font-size:.86rem;color:#5a7065}.msg{min-height:1.3em;color:#9a4d28}@media(max-width:780px){.layout{grid-template-columns:1fr}.hero{padding-top:2.5rem}}
</style></head><body><header class="hero"><div>NEIGHBORLY · LOCAL COMMUNITY BOARD</div><h1>Small acts. Stronger neighborhoods.</h1><p>Share a practical request or offer a little time, skill, or resource. Browse possible matches and coordinate safely at your own pace.</p></header><main class="wrap"><div class="layout"><section class="panel"><h2>Post to your community</h2><form id="form"><label>I'm posting a</label><select name="kind"><option value="help">Help request</option><option value="offer">Volunteer offer</option></select><label>Short title</label><input name="title" maxlength="120" required placeholder="e.g. Help carrying boxes"><label>Details</label><textarea name="description" maxlength="500" rows="3" required></textarea><label>Category</label><input name="category" maxlength="60" required placeholder="Transport, learning…"><label>Neighborhood area</label><input name="area" maxlength="60" required placeholder="Keep location general"><button>Publish post</button><p class="msg" id="msg"></p></form><p class="note">Safety first: use a general area only. Never post addresses, phone numbers, health information, or other sensitive details. Matches are suggestions, not verified people; arrange contact privately and meet in a public place.</p></section><section><div class="toolbar"><div><h2 style="margin:.2rem 0">Community board</h2><span class="meta">Fictional examples · latest first</span></div><select id="filter" style="width:auto;margin:0"><option value="all">All posts</option><option value="help">Help requests</option><option value="offer">Volunteer offers</option></select></div><div id="posts"></div></section></div></main><script>
const postsBox=document.querySelector('#posts');let posts=[];const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));async function load(){const r=await fetch('/api/posts');posts=await r.json();render()}function render(){let list=posts.filter(p=>document.querySelector('#filter').value==='all'||p.kind===document.querySelector('#filter').value);postsBox.innerHTML=list.length?list.map(p=>`<article class="card"><span class="tag">${p.kind==='help'?'HELP REQUEST':'VOLUNTEER OFFER'}</span><span class="meta"> · ${esc(p.category)} · ${esc(p.area)}</span><h3>${esc(p.title)}</h3><p>${esc(p.description)}</p><div class="toolbar"><span class="meta">Status: ${esc(p.status)}</span><span><button class="btn secondary" onclick="matches(${p.id})">Find a match</button> <select aria-label="Update status" onchange="status(${p.id},this.value)" style="width:auto;margin:0"><option ${p.status==='open'?'selected':''} value="open">Open</option><option ${p.status==='coordinating'?'selected':''} value="coordinating">Coordinating</option><option ${p.status==='resolved'?'selected':''} value="resolved">Resolved</option></select></span></div><div id="matches-${p.id}" class="meta"></div></article>`).join(''):'<div class="empty">No posts yet. Add the first one on the left.</div>'}async function matches(id){let r=await fetch('/api/matches?id='+id);let data=await r.json();document.querySelector('#matches-'+id).textContent=data.length?`Possible matches: ${data.map(x=>x.title).join(' · ')}. Similar category or neighborhood only; please use your own judgement.`:'No close matches yet. Check back later.'}async function status(id,value){await fetch('/api/posts/'+id+'/status',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:value})});load()}document.querySelector('#filter').onchange=render;document.querySelector('#form').onsubmit=async e=>{e.preventDefault();let data=Object.fromEntries(new FormData(e.target));let r=await fetch('/api/posts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let result=await r.json();document.querySelector('#msg').textContent=r.ok?'Your post is live.':result.error;if(r.ok){e.target.reset();load()}};load();
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, data, content_type='application/json; charset=utf-8'):
        body = data.encode() if isinstance(data, str) else json.dumps(data).encode()
        self.send_response(code); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body))); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/': return self.respond(200,PAGE,'text/html; charset=utf-8')
        if u.path=='/api/posts': return self.respond(200,list_posts())
        if u.path=='/api/matches':
            try: return self.respond(200,find_matches(int(parse_qs(u.query).get('id',[''])[0])))
            except (ValueError,KeyError) as e: return self.respond(400,{'error':str(e)})
        return self.respond(404,{'error':'Not found'})
    def do_POST(self):
        if urlparse(self.path).path!='/api/posts': return self.respond(404,{'error':'Not found'})
        try: return self.respond(201,create_post(self.body()))
        except (ValueError,json.JSONDecodeError) as e: return self.respond(400,{'error':str(e)})
    def do_PATCH(self):
        parts=urlparse(self.path).path.strip('/').split('/')
        if len(parts)!=4 or parts[:2]!=['api','posts'] or parts[3]!='status': return self.respond(404,{'error':'Not found'})
        try: return self.respond(200,set_status(int(parts[2]),self.body().get('status','')))
        except (ValueError,KeyError,json.JSONDecodeError) as e: return self.respond(400,{'error':str(e)})
    def log_message(self,*args): pass


def main():
    initialize(); server=ThreadingHTTPServer(('127.0.0.1',8000),Handler); print('Neighborly running at http://127.0.0.1:8000'); server.serve_forever()
if __name__=='__main__': main()
