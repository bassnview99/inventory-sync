export default function App() {
  return (
    <main className="shell">
      <header>
        <div className="mark">IS</div>
        <div><strong>Inventory Sync</strong><small>Tiendanube ↔ Mercado Libre</small></div>
        <span className="stage">ETAPA 1 · BASE</span>
      </header>
      <section className="hero">
        <p className="eyebrow">PANEL DE CONTROL</p>
        <h1>Tu inventario, bajo control.</h1>
        <p>La infraestructura está preparada. Conecta ambas plataformas en las siguientes etapas para importar tus productos y variantes.</p>
      </section>
      <section className="grid">
        <article><span>01</span><h2>Tiendanube</h2><p>Conexión pendiente</p><small>OAuth se implementará en etapa 2.</small></article>
        <article><span>02</span><h2>Mercado Libre</h2><p>Conexión pendiente</p><small>OAuth se implementará en etapa 3.</small></article>
        <article><span>03</span><h2>Catálogo</h2><p>Sin importar</p><small>La importación inicial será de solo lectura.</small></article>
      </section>
      <footer>Etapa 1 · Arquitectura y persistencia · No se modifica inventario externo.</footer>
    </main>
  );
}
