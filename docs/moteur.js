// Moteur de la version web : déchiffrement de la base et recherche plein texte.
// Utilisé par index.html (navigateur) et par tests/test_web.mjs (Node.js).
(function (exports) {
  const MAGIC = new TextEncoder().encode('RGB1');

  // En-tête : MAGIC | itérations (uint32) | sel (16 o) | nonce (12 o) | données chiffrées
  function lireEntete(octets) {
    if (MAGIC.some((x, i) => octets[i] !== x)) throw new Error('Fichier de base invalide.');
    const vue = new DataView(octets.buffer, octets.byteOffset, octets.byteLength);
    return { iterations: vue.getUint32(4), sel: octets.slice(8, 24), nonce: octets.slice(24, 36), chiffre: octets.slice(36) };
  }

  async function deriverCle(fichier, mdp, exportable) {
    const brute = await crypto.subtle.importKey('raw', new TextEncoder().encode(mdp), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt: fichier.sel, iterations: fichier.iterations },
                                   brute, { name: 'AES-GCM', length: 256 }, exportable, ['decrypt']);
  }

  async function ouvrir(fichier, cle) {
    const clair = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: fichier.nonce, additionalData: MAGIC }, cle, fichier.chiffre);
    const flux = new Blob([clair]).stream().pipeThrough(new DecompressionStream('gzip'));
    return JSON.parse(await new Response(flux).text());
  }

  const sansAccents = s => s.normalize('NFD').replace(/\p{M}/gu, '');
  const normaliser = (s, accents) => accents ? sansAccents(s.toLowerCase()) : s.toLowerCase();
  const echapper = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function preparer(donnees) {
    const base = { ...donnees, refs: [], corpus: {} };
    base.videos.forEach((v, vi) => v[2].forEach((_, bi) => base.refs.push([vi, bi])));
    construireCorpus(base, true);
    base.annees = [...new Set(base.videos.map(v => v[1]))].sort().reverse();
    return base;
  }

  // Tout le texte normalisé en une chaîne (une phrase par ligne) : une recherche = une passe regex.
  function construireCorpus(base, accents) {
    if (base.corpus[accents]) return base.corpus[accents];
    const morceaux = [], debuts = new Int32Array(base.refs.length);
    let pos = 0, k = 0;
    for (const v of base.videos) for (const b of v[2]) {
      const n = normaliser(b[1], accents);
      debuts[k++] = pos; morceaux.push(n); pos += n.length + 1;
    }
    return base.corpus[accents] = { texte: morceaux.join('\n'), debuts };
  }

  function trouverBloc(debuts, pos) {
    let lo = 0, hi = debuts.length - 1;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (debuts[mid] <= pos) lo = mid; else hi = mid - 1; }
    return lo;
  }

  // Les positions trouvées sont dans le texte normalisé : on les ramène au texte original.
  function surligner(texte, spans, accents) {
    const correspondance = [0];
    let n = 0, i = 0;
    for (const c of texte) {
      n += normaliser(c, accents).length; i += c.length;
      while (correspondance.length <= n) correspondance.push(i);
    }
    const orig = x => correspondance[Math.min(x, correspondance.length - 1)];
    let out = '', pos = 0;
    for (const [d, f] of spans) {
      const od = orig(d), of = orig(f);
      if (od < pos) continue;
      out += echapper(texte.slice(pos, od)) + '<mark>' + echapper(texte.slice(od, of)) + '</mark>'; pos = of;
    }
    return out + echapper(texte.slice(pos));
  }

  function rechercher(base, termes, { annees = null, motEntier = false, accents = true, limite = 300 } = {}) {
    const t = [...new Set(termes.map(x => normaliser(x.trim(), accents)).filter(Boolean))].sort((a, b) => b.length - a.length);
    if (!t.length) return { resultats: [], total: 0, videos: 0 };
    const alt = t.map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const motif = new RegExp(motEntier ? `(?<![\\p{L}\\p{N}_])(?:${alt})(?![\\p{L}\\p{N}_])` : alt, 'gu');
    const { texte, debuts } = construireCorpus(base, accents);
    const filtre = annees ? new Set(annees) : null;

    const trouves = new Map();
    for (const m of texte.matchAll(motif)) {
      const k = trouverBloc(debuts, m.index);
      const d = m.index - debuts[k];
      if (!trouves.has(k)) trouves.set(k, []);
      trouves.get(k).push([d, d + m[0].length]);
    }
    const resultats = []; let total = 0; const videos = new Set();
    for (const [k, spans] of trouves) {
      const [vi, bi] = base.refs[k];
      const v = base.videos[vi];
      if (filtre && !filtre.has(v[1])) continue;
      total++; videos.add(vi);
      if (resultats.length >= limite) continue;
      const blocs = v[2], contexte = [];
      for (let j = Math.max(0, bi - 2); j < Math.min(blocs.length, bi + 3); j++)
        contexte.push({ temps: blocs[j][0], html: j === bi ? surligner(blocs[j][1], spans, accents) : echapper(blocs[j][1]), trouve: j === bi });
      const lien = base.liens[v[0]];
      resultats.push({ titre: v[0], temps: blocs[bi][0], contexte, lien: typeof lien === 'string' && /^https?:\/\//.test(lien) ? lien : null });
    }
    return { resultats, total, videos: videos.size };
  }

  Object.assign(exports, { lireEntete, deriverCle, ouvrir, preparer, rechercher, echapper });
})(typeof module !== 'undefined' ? module.exports : (window.Moteur = {}));
