"""
3ioNetra Conversation Viewer — Standalone read-only admin tool.
Connects to the same MongoDB as the main backend and displays
users and their conversations in a clean web UI.

Run: python app.py
Open: http://localhost:8081
"""

import os
from pathlib import Path
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Configuration & MongoDB
# ---------------------------------------------------------------------------

# Load .env from backend directory
_env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

MONGODB_URI = os.getenv("MONGODB_URI", "")
DATABASE_NAME = os.getenv("DATABASE_NAME", "")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")

if not MONGODB_URI or not DATABASE_NAME:
    raise RuntimeError(
        "MONGODB_URI and DATABASE_NAME must be set. "
        f"Looked for .env at {_env_path}"
    )

_mongo_uri = MONGODB_URI
if DATABASE_PASSWORD:
    _mongo_uri = _mongo_uri.replace("<db_password>", DATABASE_PASSWORD)

_client = MongoClient(_mongo_uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
try:
    _client.admin.command("ping")
    print(f"Connected to MongoDB database: {DATABASE_NAME}")
except Exception as e:
    print(f"Warning: MongoDB ping failed ({e}), will retry on first request")
db = _client[DATABASE_NAME]

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(title="3ioNetra Conversation Viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def serialize(doc):
    """Recursively convert MongoDB types to JSON-safe values."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if k == "_id":
                out["_id"] = str(v)
            elif isinstance(v, ObjectId):
                out[k] = str(v)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                out[k] = serialize(v)
            else:
                out[k] = v
        return out
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

ALLOWED_EMAILS = [
    "tejal@3ionetra.com",
    "satish.mishra@3ionetra.com",
    "priyanka.satim@3ionetra.com",
    "chandan.yadav@3ionetra.com",
    "tejashree.ambare@3ionetra.com",
    "rahul.dube@3ionetra.com",
    "lakshmi@3ionetra.com",
    "anushree02@gmail.com",
    "amit.pandey.6869@gmail.com",
    "user199@example.com",
    "testerbeta123@netra.com",
]


@app.get("/api/users")
def list_users():
    """List only the 11 specified users (no password fields)."""
    users = list(
        db.users.find(
            {"email": {"$in": ALLOWED_EMAILS}},
            {"password_hash": 0, "password_salt": 0},
        ).sort("created_at", -1)
    )
    return serialize(users)


@app.get("/api/users/{user_id}/conversations")
def list_conversations(user_id: str):
    """List conversations for a user, sorted by most recent."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$sort": {"updated_at": -1}},
        {
            "$project": {
                "session_id": 1,
                "last_title": 1,
                "title": 1,
                "created_at": 1,
                "updated_at": 1,
                "message_count": {"$size": {"$ifNull": ["$messages", []]}},
                "conversation_summary": 1,
            }
        },
    ]
    convos = list(db.conversations.aggregate(pipeline))
    # Normalize title field
    for c in convos:
        c["title"] = c.get("last_title") or c.get("title") or "Untitled"
    return serialize(convos)


@app.get("/api/conversations/{session_id}")
def get_conversation(session_id: str):
    """Get full conversation with messages and memory."""
    doc = db.conversations.find_one({"session_id": session_id})
    if not doc:
        raise HTTPException(404, "Conversation not found")
    doc["title"] = doc.get("last_title") or doc.get("title") or "Untitled"
    return serialize(doc)


# ---------------------------------------------------------------------------
# HTML UI (embedded single-page app)
# ---------------------------------------------------------------------------

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3ioNetra — Conversation Viewer</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { font-family: 'Inter', system-ui, sans-serif; }
  .user-card:hover { background-color: #eef2ff; }
  .user-card.active { background-color: #e0e7ff; border-right: 3px solid #4f46e5; }
  .convo-card:hover { background-color: #f9fafb; transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .bubble-user { background: #4f46e5; color: white; border-radius: 18px 18px 4px 18px; }
  .bubble-assistant { background: white; color: #1f2937; border: 1px solid #e5e7eb; border-radius: 18px 18px 18px 4px; }
  .scroll-area { overflow-y: auto; }
  .scroll-area::-webkit-scrollbar { width: 6px; }
  .scroll-area::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
  .fade-in { animation: fadeIn 0.2s ease-in; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .tag { display: inline-block; padding: 2px 10px; border-radius: 9999px; font-size: 0.75rem; margin: 2px; }
</style>
</head>
<body class="bg-gray-50 h-screen flex flex-col">

<!-- Header -->
<header class="bg-indigo-700 text-white px-6 py-3 flex items-center justify-between shadow-md flex-shrink-0">
  <div class="flex items-center gap-3">
    <div class="w-9 h-9 bg-indigo-500 rounded-lg flex items-center justify-center font-bold text-lg">3</div>
    <div>
      <h1 class="text-lg font-semibold leading-tight">3ioNetra — Conversation Viewer</h1>
      <p class="text-indigo-200 text-xs">Read-only admin tool</p>
    </div>
  </div>
  <div id="stats" class="text-indigo-200 text-sm"></div>
</header>

<!-- Main layout -->
<div class="flex flex-1 overflow-hidden">

  <!-- Left: User list -->
  <aside id="user-panel" class="w-72 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
    <div class="px-4 py-3 border-b border-gray-100">
      <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">Users</h2>
    </div>
    <div id="user-list" class="scroll-area flex-1"></div>
  </aside>

  <!-- Center: Conversations / Chat -->
  <main id="center-panel" class="flex-1 flex flex-col overflow-hidden bg-gray-50">
    <div id="center-content" class="flex-1 scroll-area">
      <div class="flex items-center justify-center h-full text-gray-400">
        <div class="text-center">
          <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
          </svg>
          <p class="text-lg">Select a user to view conversations</p>
        </div>
      </div>
    </div>
  </main>

  <!-- Right: User details -->
  <aside id="detail-panel" class="w-80 bg-white border-l border-gray-200 flex-col flex-shrink-0 hidden">
    <div id="user-details" class="scroll-area flex-1 p-5"></div>
  </aside>

</div>

<script>
// ── State ──
let users = [];
let selectedUserId = null;
let selectedSessionId = null;

// ── Color palette for avatars ──
const COLORS = ['#4f46e5','#7c3aed','#db2777','#ea580c','#d97706','#059669','#0891b2','#2563eb','#9333ea','#e11d48'];
function hashColor(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
  return COLORS[Math.abs(h) % COLORS.length];
}

function initials(user) {
  const f = (user.first_name || '')[0] || '';
  const l = (user.last_name || '')[0] || '';
  return (f + l).toUpperCase() || '?';
}

function fullName(user) {
  return [user.first_name, user.middle_name, user.last_name].filter(Boolean).join(' ') || 'Unknown';
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function relativeTime(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  const days = Math.floor(hrs / 24);
  return days + 'd ago';
}

// ── API helpers ──
async function api(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Render: User List ──
function renderUserList() {
  const el = document.getElementById('user-list');
  el.innerHTML = users.map(u => `
    <div class="user-card px-4 py-3 cursor-pointer border-b border-gray-50 transition-all ${u.id === selectedUserId ? 'active' : ''}"
         onclick="selectUser('${u.id}')">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0"
             style="background:${hashColor(u.id)}">
          ${initials(u)}
        </div>
        <div class="min-w-0">
          <div class="font-medium text-gray-900 text-sm truncate">${fullName(u)}</div>
          <div class="text-xs text-gray-400 truncate">${u.email || ''}</div>
        </div>
        ${u.is_active ? '<div class="w-2.5 h-2.5 bg-green-400 rounded-full ml-auto flex-shrink-0" title="Active"></div>' : ''}
      </div>
    </div>
  `).join('');
  document.getElementById('stats').textContent = users.length + ' users';
}

// ── Render: User Details (right panel) ──
function renderUserDetails(user) {
  const panel = document.getElementById('detail-panel');
  const el = document.getElementById('user-details');
  panel.classList.remove('hidden');
  panel.classList.add('flex');

  const sp = user.spiritual_profile || {};
  const deities = (user.deities || []).filter(Boolean);
  const temples = (user.temples || []).map(t => t.temple_id || t).filter(Boolean);
  const purchases = (user.purchases || []).map(p => p.name || p.product_id || '').filter(Boolean);

  el.innerHTML = `
    <div class="text-center mb-5">
      <div class="w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-xl mx-auto mb-3"
           style="background:${hashColor(user.id)}">
        ${initials(user)}
      </div>
      <h3 class="font-semibold text-gray-900 text-lg">${fullName(user)}</h3>
      <p class="text-sm text-gray-500">${user.occupation || '—'}</p>
    </div>

    <div class="space-y-4 text-sm">
      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Contact</h4>
        <div class="space-y-1">
          <div class="flex justify-between"><span class="text-gray-500">Email</span><span class="text-gray-800 truncate ml-2">${user.email || '—'}</span></div>
          <div class="flex justify-between"><span class="text-gray-500">Phone</span><span class="text-gray-800">${user.phone || '—'}</span></div>
        </div>
      </section>

      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Personal</h4>
        <div class="space-y-1">
          <div class="flex justify-between"><span class="text-gray-500">Gender</span><span class="text-gray-800 capitalize">${user.gender || '—'}</span></div>
          <div class="flex justify-between"><span class="text-gray-500">DOB</span><span class="text-gray-800">${user.date_of_birth || '—'}</span></div>
        </div>
      </section>

      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Spiritual Profile</h4>
        <div class="space-y-1">
          <div class="flex justify-between"><span class="text-gray-500">Rashi</span><span class="text-gray-800">${sp.rashi || '—'}</span></div>
          <div class="flex justify-between"><span class="text-gray-500">Gotra</span><span class="text-gray-800">${sp.gotra || '—'}</span></div>
          <div class="flex justify-between"><span class="text-gray-500">Nakshatra</span><span class="text-gray-800">${sp.nakshatra || '—'}</span></div>
        </div>
      </section>

      ${deities.length ? `
      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Deities</h4>
        <div class="flex flex-wrap">${deities.map(d => `<span class="tag bg-amber-100 text-amber-800">${d}</span>`).join('')}</div>
      </section>` : ''}

      ${temples.length ? `
      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Temples</h4>
        <div class="flex flex-wrap">${temples.map(t => `<span class="tag bg-indigo-100 text-indigo-800">${t}</span>`).join('')}</div>
      </section>` : ''}

      ${purchases.length ? `
      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Purchases</h4>
        <div class="flex flex-wrap">${purchases.map(p => `<span class="tag bg-green-100 text-green-800">${p}</span>`).join('')}</div>
      </section>` : ''}

      <section>
        <h4 class="font-semibold text-gray-500 text-xs uppercase tracking-wide mb-2">Account</h4>
        <div class="space-y-1">
          <div class="flex justify-between"><span class="text-gray-500">Joined</span><span class="text-gray-800">${fmtDate(user.created_at)}</span></div>
          <div class="flex justify-between"><span class="text-gray-500">Status</span>
            <span class="${user.is_active ? 'text-green-600' : 'text-red-500'}">${user.is_active ? 'Active' : 'Inactive'}</span>
          </div>
        </div>
      </section>
    </div>
  `;
}

// ── Render: Conversation List ──
function renderConversationList(convos, user) {
  const el = document.getElementById('center-content');
  if (!convos.length) {
    el.innerHTML = `
      <div class="flex items-center justify-center h-full text-gray-400">
        <div class="text-center">
          <p class="text-lg mb-1">No conversations found</p>
          <p class="text-sm">${fullName(user)} has no saved conversations yet.</p>
        </div>
      </div>`;
    return;
  }

  el.innerHTML = `
    <div class="p-6 fade-in">
      <div class="flex items-center justify-between mb-5">
        <h2 class="text-xl font-semibold text-gray-800">${fullName(user)}'s Conversations</h2>
        <span class="text-sm text-gray-400">${convos.length} conversation${convos.length !== 1 ? 's' : ''}</span>
      </div>
      <div class="grid gap-3">
        ${convos.map(c => `
          <div class="convo-card bg-white rounded-xl p-4 border border-gray-100 cursor-pointer transition-all"
               onclick="selectConversation('${c.session_id}')">
            <div class="flex items-start justify-between">
              <div class="min-w-0 flex-1">
                <h3 class="font-medium text-gray-900 truncate">${c.title}</h3>
                ${c.conversation_summary ? `<p class="text-sm text-gray-500 mt-1 line-clamp-2">${c.conversation_summary}</p>` : ''}
              </div>
              <span class="ml-3 px-2.5 py-0.5 bg-indigo-50 text-indigo-700 rounded-full text-xs font-medium flex-shrink-0">
                ${c.message_count} msg${c.message_count !== 1 ? 's' : ''}
              </span>
            </div>
            <div class="flex items-center gap-4 mt-3 text-xs text-gray-400">
              <span>Created ${fmtDate(c.created_at)}</span>
              <span>Updated ${relativeTime(c.updated_at)}</span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>`;
}

// ── Render: Chat Thread ──
function renderChatThread(convo) {
  const user = users.find(u => u.id === convo.user_id);
  const userName = user ? user.first_name : 'User';
  const messages = convo.messages || [];
  const memory = convo.memory || {};
  const story = memory.story || {};
  const emotionalArc = memory.emotional_arc || [];
  const concepts = memory.relevant_concepts || [];
  const quotes = memory.user_quotes || [];

  const el = document.getElementById('center-content');
  el.innerHTML = `
    <div class="flex flex-col h-full fade-in">
      <!-- Chat header -->
      <div class="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 flex-shrink-0">
        <button onclick="backToConversations()" class="text-indigo-600 hover:text-indigo-800 mr-1" title="Back">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
          </svg>
        </button>
        <div>
          <h2 class="font-semibold text-gray-900 text-sm">${convo.title}</h2>
          <p class="text-xs text-gray-400">${messages.length} messages &middot; ${fmtDate(convo.created_at)}</p>
        </div>
      </div>

      <!-- Messages -->
      <div class="flex-1 overflow-y-auto px-6 py-4 space-y-3" id="chat-messages">
        ${messages.map(m => {
          const isUser = m.role === 'user';
          return `
            <div class="flex ${isUser ? 'justify-end' : 'justify-start'}">
              <div class="max-w-[75%]">
                <div class="text-xs mb-1 ${isUser ? 'text-right text-gray-400' : 'text-left text-gray-400'}">
                  ${isUser ? userName : 'Mitra'}
                  ${m.timestamp ? ' &middot; ' + fmtTime(m.timestamp) : ''}
                </div>
                <div class="${isUser ? 'bubble-user' : 'bubble-assistant'} px-4 py-2.5 text-sm leading-relaxed shadow-sm">
                  ${escapeHtml(m.content)}
                </div>
              </div>
            </div>`;
        }).join('')}
      </div>

      <!-- Memory & Context (collapsible) -->
      ${(Object.keys(story).length || emotionalArc.length || concepts.length) ? `
      <div class="border-t border-gray-200 bg-white flex-shrink-0">
        <button onclick="toggleMemory()" class="w-full px-6 py-2.5 text-left text-sm font-medium text-gray-600 hover:text-gray-800 flex items-center justify-between">
          <span>Memory &amp; Context</span>
          <svg id="memory-chevron" class="w-4 h-4 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div id="memory-section" class="hidden px-6 pb-4 text-sm space-y-3 max-h-64 overflow-y-auto">
          ${story.primary_concern || story.emotional_state || story.life_area ? `
          <div>
            <h4 class="font-semibold text-gray-500 text-xs uppercase mb-1">Story</h4>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-gray-700">
              ${story.primary_concern ? `<span><b>Concern:</b> ${story.primary_concern}</span>` : ''}
              ${story.emotional_state ? `<span><b>Emotion:</b> ${story.emotional_state}</span>` : ''}
              ${story.life_area ? `<span><b>Life area:</b> ${story.life_area}</span>` : ''}
              ${story.trigger_event ? `<span><b>Trigger:</b> ${story.trigger_event}</span>` : ''}
            </div>
          </div>` : ''}

          ${emotionalArc.length ? `
          <div>
            <h4 class="font-semibold text-gray-500 text-xs uppercase mb-1">Emotional Arc</h4>
            <div class="flex flex-wrap gap-1">
              ${emotionalArc.map(e => `<span class="tag bg-purple-100 text-purple-800">T${e.turn}: ${e.emotion}</span>`).join('')}
            </div>
          </div>` : ''}

          ${concepts.length ? `
          <div>
            <h4 class="font-semibold text-gray-500 text-xs uppercase mb-1">Dharmic Concepts</h4>
            <div class="flex flex-wrap gap-1">
              ${concepts.map(c => `<span class="tag bg-amber-100 text-amber-800">${c}</span>`).join('')}
            </div>
          </div>` : ''}

          ${quotes.length ? `
          <div>
            <h4 class="font-semibold text-gray-500 text-xs uppercase mb-1">Notable Quotes</h4>
            <div class="space-y-1">
              ${quotes.map(q => `<p class="text-gray-600 italic">"${escapeHtml(q.quote || q)}" <span class="text-gray-400 text-xs">(turn ${q.turn || '?'})</span></p>`).join('')}
            </div>
          </div>` : ''}

          ${convo.conversation_summary ? `
          <div>
            <h4 class="font-semibold text-gray-500 text-xs uppercase mb-1">Summary</h4>
            <p class="text-gray-700">${escapeHtml(convo.conversation_summary)}</p>
          </div>` : ''}
        </div>
      </div>` : ''}
    </div>`;

  // Scroll to bottom of chat
  const chatEl = document.getElementById('chat-messages');
  if (chatEl) chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function toggleMemory() {
  const sec = document.getElementById('memory-section');
  const chev = document.getElementById('memory-chevron');
  sec.classList.toggle('hidden');
  chev.style.transform = sec.classList.contains('hidden') ? '' : 'rotate(180deg)';
}

// ── Actions ──
async function selectUser(userId) {
  selectedUserId = userId;
  selectedSessionId = null;
  renderUserList();
  const user = users.find(u => u.id === userId);
  renderUserDetails(user);
  const convos = await api('/api/users/' + userId + '/conversations');
  renderConversationList(convos, user);
}

async function selectConversation(sessionId) {
  selectedSessionId = sessionId;
  const convo = await api('/api/conversations/' + sessionId);
  renderChatThread(convo);
}

function backToConversations() {
  if (selectedUserId) selectUser(selectedUserId);
}

// ── Init ──
(async function() {
  users = await api('/api/users');
  renderUserList();
})();
</script>

</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return HTML_PAGE


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=port == 8081)
