export const API_BASE=(process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000").replace(/\/$/,"");
let csrfToken="";
let csrfBootstrapPromise:Promise<void>|null=null;

function updateCsrfToken(value:unknown):void {
  if(typeof value==="object"&&value!==null&&"csrf_token" in value) {
    const candidate=(value as {csrf_token?:unknown}).csrf_token;
    if(typeof candidate==="string") csrfToken=candidate;
  }
}

/**
 * CSRF tokens are returned by authenticated session endpoints, not placed in
 * readable cookies. A hard navigation directly to a workspace subpage resets
 * this module's in-memory token, so bootstrap it from the current session
 * before the first unsafe request. If there is no session, leave the token
 * empty and allow the requested endpoint to return its normal auth response.
 */
async function bootstrapCsrfToken():Promise<void> {
  if(csrfToken) return;
  if(!csrfBootstrapPromise) {
    csrfBootstrapPromise=(async()=>{
      try {
        const response=await fetch(API_BASE+"/api/auth/me",{
          method:"GET",
          credentials:"include",
          cache:"no-store",
          headers:{Accept:"application/json"}
        });
        if(!response.ok) return;
        const data:unknown=await response.json();
        updateCsrfToken(data);
      } catch {
        // Preserve the original API request as the authoritative error surface.
      }
    })();
  }
  const pending=csrfBootstrapPromise;
  try {
    await pending;
  } finally {
    if(csrfBootstrapPromise===pending) csrfBootstrapPromise=null;
  }
}

export async function apiFetch<T=unknown>(path:string,init:RequestInit={}):Promise<T> {
  const headers=new Headers(init.headers||{});
  const method=(init.method||"GET").toUpperCase();
  const unsafeMethod=![ "GET","HEAD","OPTIONS","TRACE" ].includes(method);
  if(init.body&&!headers.has("Content-Type")) headers.set("Content-Type","application/json");
  if(unsafeMethod&&!csrfToken) await bootstrapCsrfToken();
  if(unsafeMethod&&csrfToken&&!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token",csrfToken);

  const response=await fetch(API_BASE+path,{...init,method,headers,credentials:"include",cache:"no-store"});
  const text=await response.text();
  let data:unknown=null;
  if(text) {
    try { data=JSON.parse(text); } catch { data=text; }
  }
  updateCsrfToken(data);
  if(path==="/api/auth/logout"&&response.ok) csrfToken="";
  if(!response.ok) {
    const detail=typeof data==="object"&&data!==null&&"detail" in data
      ?String((data as {detail:unknown}).detail)
      :String(data||response.statusText);
    throw new Error(`${response.status}: ${detail}`);
  }
  return data as T;
}

export function websocketURL(path="/ws"):string {
  return `${API_BASE.replace(/^http/,"ws")}${path}`;
}
