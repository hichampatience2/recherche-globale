// Test du moteur web : node tests/test_web.mjs
// Mesure sur une vraie base : RG_BENCH=chemin/donnees.bin RG_MOT_DE_PASSE=... node tests/test_web.mjs
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const Moteur = createRequire(import.meta.url)(join(racine, 'docs', 'moteur.js'));

async function charger(chemin, mdp) {
  const fichier = Moteur.lireEntete(new Uint8Array(readFileSync(chemin)));
  return Moteur.preparer(await Moteur.ouvrir(fichier, await Moteur.deriverCle(fichier, mdp, false)));
}

if (process.env.RG_BENCH) {
  let t = performance.now();
  const base = await charger(process.env.RG_BENCH, process.env.RG_MOT_DE_PASSE);
  console.log(`ouverture + préparation : ${((performance.now() - t) / 1000).toFixed(1)} s, ${base.videos.length} vidéos, ${base.refs.length} phrases`);
  for (const q of [['priere'], ['coran', 'bible'], ['messie']]) {
    t = performance.now();
    const r = Moteur.rechercher(base, q);
    console.log(q.join(','), r.total, r.videos, `${(performance.now() - t).toFixed(0)} ms`);
  }
  process.exit(0);
}

const tmp = mkdtempSync(join(tmpdir(), 'rg-'));
try {
  const sortie = join(tmp, 'donnees.bin');
  execFileSync('python', [join(racine, 'construire_site.py'), join(racine, 'exemple', 'FUSION_EXEMPLE.txt'),
    '--liens', join(racine, 'exemple', 'liens.exemple.json'), '--sortie', sortie],
    { env: { ...process.env, RG_MOT_DE_PASSE: 'motdepasse-test', PYTHONIOENCODING: 'utf-8' }, stdio: 'ignore' });

  await assert.rejects(charger(sortie, 'mauvais'), 'un mauvais mot de passe doit être refusé');
  const base = await charger(sortie, 'motdepasse-test');

  assert.equal(base.videos.length, 2);
  assert.deepEqual(base.annees, ['2024', '2019']);
  assert.ok(base.videos[0][2][0][1].startsWith('Bonjour'), 'message TurboScribe retiré');

  assert.equal(Moteur.rechercher(base, ['priere']).total, 2);
  assert.equal(Moteur.rechercher(base, ['priere'], { accents: false }).total, 0);
  assert.equal(Moteur.rechercher(base, ['ecol'], { motEntier: true }).total, 0);
  assert.equal(Moteur.rechercher(base, ['coran', 'vendredi'], { annees: ['2019'] }).total, 1);

  const r = Moteur.rechercher(base, ['ecole']).resultats[0];
  assert.ok(r.contexte.find(c => c.trouve).html.includes('<mark>ÉCOLE</mark>'), 'surlignage sur le texte original');
  assert.equal(r.lien, 'https://odysee.com/@chaine/video-exemple');

  console.log('Tous les tests du moteur web passent.');
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
