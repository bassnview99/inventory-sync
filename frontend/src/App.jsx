import { useCallback, useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const KEY_STORAGE = "inventory-sync-admin-key";

const RESULT_MESSAGES = {
  connected: ["ok", "Tiendanube conectada correctamente."],
  error_invalid_state: ["error", "La autorización caducó o no es válida. Vuelve a pulsar Conectar."],
  error_token_exchange: ["error", "Tiendanube rechazó el código de autorización. Inténtalo de nuevo."],
  error_missing_params: ["error", "Tiendanube no devolvió los datos esperados."],
};

function loadKey() {
  try { return sessionStorage.getItem(KEY_STORAGE) || ""; } catch { return ""; }
}

async function api(path, adminKey, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "X-Admin-Key": adminKey, "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch { /* sin cuerpo */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "—");

export default function App() {
  const [adminKey, setAdminKey] = useState(loadKey);
  const [keyDraft, setKeyDraft] = useState("");
  const [connections, setConnections] = useState(null);
  const [stats, setStats] = useState(null);
  const [variants, setVariants] = useState({ total: 0, items: [] });
  const [jobs, setJobs] = useState([]);
  const [query, setQuery] = useState("");
  const [onlyNoSku, setOnlyNoSku] = useState(false);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const limit = 50;

  const tiendanube = connections?.connections.find((c) => c.platform === "tiendanube");
  const mercadolibre = connections?.connections.find((c) => c.platform === "mercadolibre");
  const connected = tiendanube?.status === "connected";

  // Resultado de la redirección OAuth (?tiendanube=connected|error_...).
  useEffect(() => {
    const result = new URLSearchParams(window.location.search).get("tiendanube");
    if (result && RESULT_MESSAGES[result]) {
      const [kind, text] = RESULT_MESSAGES[result];
      setNotice({ kind, text });
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const handleError = useCallback((error) => {
    if (error.status === 401) {
      try { sessionStorage.removeItem(KEY_STORAGE); } catch { /* ignorar */ }
      setAdminKey("");
      setNotice({ kind: "error", text: "Clave de administración incorrecta." });
    } else {
      setNotice({ kind: "error", text: error.message });
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!adminKey) return;
    try {
      const [conn, st, jb] = await Promise.all([
        api("/api/connections", adminKey),
        api("/api/catalog/tiendanube/stats", adminKey),
        api("/api/sync/jobs?limit=10", adminKey),
      ]);
      setConnections(conn); setStats(st); setJobs(jb.items);
    } catch (error) { handleError(error); }
  }, [adminKey, handleError]);

  const loadVariants = useCallback(async () => {
    if (!adminKey) return;
    const params = new URLSearchParams({ platform: "tiendanube", limit, offset });
    if (query.trim()) params.set("q", query.trim());
    if (onlyNoSku) params.set("only_without_sku", "true");
    try { setVariants(await api(`/api/catalog/variants?${params}`, adminKey)); } catch (error) { handleError(error); }
  }, [adminKey, query, onlyNoSku, offset, handleError]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { const t = setTimeout(loadVariants, 250); return () => clearTimeout(t); }, [loadVariants]);

  const saveKey = (event) => {
    event.preventDefault();
    try { sessionStorage.setItem(KEY_STORAGE, keyDraft.trim()); } catch { /* ignorar */ }
    setAdminKey(keyDraft.trim()); setKeyDraft(""); setNotice(null);
  };

  const connect = async () => {
    setBusy(true);
    try {
      const { authorize_url } = await api("/api/connections/tiendanube/authorize", adminKey, { method: "POST" });
      window.location.href = authorize_url;
    } catch (error) { handleError(error); setBusy(false); }
  };

  const disconnect = async () => {
    if (!window.confirm("¿Desconectar Tiendanube? Se borra el token guardado; el catálogo importado se conserva.")) return;
    try { await api("/api/connections/tiendanube", adminKey, { method: "DELETE" }); await refresh(); } catch (error) { handleError(error); }
  };

  const importCatalog = async () => {
    setBusy(true); setNotice(null);
    try {
      const job = await api("/api/catalog/tiendanube/import", adminKey, { method: "POST" });
      if (job.status === "completed") {
        const d = job.logs[0]?.details || {};
        setNotice({ kind: "ok", text: `Importación lista: ${d.total} variantes (${d.created} nuevas, ${d.updated} actualizadas, ${d.deactivated} ya no existen).` });
      } else {
        setNotice({ kind: "error", text: `La importación falló: ${job.error_message}` });
      }
      setOffset(0);
      await Promise.all([refresh(), loadVariants()]);
    } catch (error) { handleError(error); } finally { setBusy(false); }
  };

  if (!adminKey) {
    return (
      <main className="shell narrow">
        <header><div className="mark">IS</div><div><strong>Inventory Sync</strong><small>Tiendanube ↔ Mercado Libre</small></div></header>
        <section className="hero compact">
          <p className="eyebrow">ACCESO</p>
          <h1>Clave de administración</h1>
          <p>Introduce el valor de <code>ADMIN_API_KEY</code> configurado en el servidor. Se guarda solo en esta pestaña.</p>
        </section>
        {notice && <p className={`notice ${notice.kind}`}>{notice.text}</p>}
        <form className="keyform" onSubmit={saveKey}>
          <input type="password" autoFocus value={keyDraft} onChange={(e) => setKeyDraft(e.target.value)} placeholder="ADMIN_API_KEY" />
          <button className="primary" disabled={!keyDraft.trim()}>Entrar</button>
        </form>
      </main>
    );
  }

  return (
    <main className="shell">
      <header>
        <div className="mark">IS</div>
        <div><strong>Inventory Sync</strong><small>Tiendanube ↔ Mercado Libre</small></div>
        <span className="stage">ETAPA 2 · TIENDANUBE</span>
      </header>

      {notice && <p className={`notice ${notice.kind}`} role="status">{notice.text}</p>}

      <section className="grid">
        <article>
          <span>01</span><h2>Tiendanube</h2>
          <p className={`status ${tiendanube?.status || "disconnected"}`}>
            {connected ? "Conectada" : tiendanube?.status === "error" ? "Requiere reconexión" : "Sin conectar"}
          </p>
          {connected && <small>Tienda {tiendanube.account_id} · permisos: {tiendanube.scopes || "—"}<br />Desde {fmt(tiendanube.connected_at)}</small>}
          <div className="actions">
            <button className="primary" onClick={connect} disabled={busy}>{connected ? "Reautorizar" : "Conectar"}</button>
            {connected && <button onClick={disconnect}>Desconectar</button>}
          </div>
        </article>
        <article>
          <span>02</span><h2>Mercado Libre</h2>
          <p className="status disconnected">{mercadolibre?.status === "connected" ? "Conectada" : "Pendiente"}</p>
          <small>La conexión con Mercado Libre llega en la etapa 3.</small>
        </article>
        <article>
          <span>03</span><h2>Catálogo Tiendanube</h2>
          <p>{stats ? `${stats.variants} variantes` : "…"}</p>
          {stats && stats.variants > 0 && (
            <small>{stats.without_sku} sin SKU · {stats.unmanaged_stock} sin control de stock<br />Última lectura: {fmt(stats.last_synced_at)}</small>
          )}
          <div className="actions">
            <button className="primary" onClick={importCatalog} disabled={busy || !connected}>
              {busy ? "Importando…" : "Importar catálogo"}
            </button>
          </div>
          <small className="hint">Solo lectura: no modifica nada en Tiendanube.</small>
        </article>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Variantes importadas</h2>
          <div className="filters">
            <input type="search" placeholder="Buscar por SKU o nombre" value={query}
                   onChange={(e) => { setQuery(e.target.value); setOffset(0); }} />
            <label><input type="checkbox" checked={onlyNoSku} onChange={(e) => { setOnlyNoSku(e.target.checked); setOffset(0); }} /> Solo sin SKU</label>
          </div>
        </div>
        {variants.items.length === 0 ? (
          <p className="empty">{connected ? "No hay variantes. Pulsa «Importar catálogo»." : "Conecta Tiendanube para importar tu catálogo."}</p>
        ) : (
          <>
            <table>
              <thead><tr><th>Producto</th><th>Variante</th><th>SKU</th><th className="num">Stock</th><th>Estado</th></tr></thead>
              <tbody>
                {variants.items.map((v) => (
                  <tr key={v.id}>
                    <td>{v.product_name}</td>
                    <td>{v.variant_name || "—"}</td>
                    <td>{v.sku ? <code>{v.sku}</code> : <em className="warn">sin SKU</em>}</td>
                    <td className="num">{v.stock === null ? <em>sin control</em> : v.stock}</td>
                    <td>{v.published ? "Publicado" : "Oculto"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pager">
              <span>{offset + 1}–{Math.min(offset + limit, variants.total)} de {variants.total}</span>
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Anterior</button>
              <button disabled={offset + limit >= variants.total} onClick={() => setOffset(offset + limit)}>Siguiente</button>
            </div>
          </>
        )}
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Historial de importaciones</h2></div>
        {jobs.length === 0 ? <p className="empty">Todavía no hay importaciones.</p> : (
          <table>
            <thead><tr><th>Fecha</th><th>Tipo</th><th>Estado</th><th>Detalle</th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{fmt(j.created_at)}</td>
                  <td>{j.job_type === "catalog_import" ? "Importar catálogo" : j.job_type}</td>
                  <td><span className={`pill ${j.status}`}>{j.status === "completed" ? "Completada" : j.status === "failed" ? "Falló" : j.status}</span></td>
                  <td>{j.error_message || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <footer>
        Etapa 2 · Tiendanube en solo lectura · La comparación de stock y la sincronización llegan en las etapas 4 y 5.
        <button className="link" onClick={() => { try { sessionStorage.removeItem(KEY_STORAGE); } catch { /* ignorar */ } setAdminKey(""); }}>Cerrar sesión</button>
      </footer>
    </main>
  );
}
