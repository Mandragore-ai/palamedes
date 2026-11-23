/**
 * MCDice → journal en direct du Barde (lu par le Mentor et le Sage en direct).
 * Regroupe les dés lancés ensemble (ex. 2d6 PbtA) et produit une ligne de journal datée
 * sur la même horloge que les répliques (`arrivedMs` = ms depuis l'ouverture du flux).
 * Licence : CC BY-NC 4.0.
 */
import type { MCDice, ResultatDe } from "./mcdice";

/** Ligne proposée pour `BardLiveEvents.event` (à ajouter au type JournalRow de lib/bard-live/journal.mts). */
export type JournalRollRow = {
  action: "roll";
  roll: {
    atMs: number;            // même horloge que turn.arrivedMs
    owner: { kind: "character"; id: string } | { kind: "gm" } | null;  // fiche de personnage associée au dé, ou dé du MJ
    dice: { die: string; faces: number; value: number }[];
    sum: number;             // somme brute des dés, sans caractéristique : le Mentor l'ajoute depuis la fiche
    source: "ble" | "tablette";
  };
};

export interface OptionsRegroupement {
  fenetreMs?: number;                         // dés arrêtés à moins de cette durée = un seul jet (défaut 1500 ms)
  debutFluxMs: number;                        // performance.now() à l'ouverture du flux du Barde
  proprietaire: (nomDe: string) => JournalRollRow["roll"]["owner"]; // association dé → fiche de personnage ou MJ
  emettre: (row: JournalRollRow) => void;     // ex. pousser dans la file envoyée par action « events »
}

/** Écoute plusieurs dés et émet un jet par groupe (même propriétaire, dans la fenêtre). Renvoie la fonction d'arrêt. */
export function regrouperJets(des: MCDice[], o: OptionsRegroupement): () => void {
  const fenetre = o.fenetreMs ?? 1500;
  type Groupe = { premier: number; owner: JournalRollRow["roll"]["owner"]; des: JournalRollRow["roll"]["dice"]; minuterie: ReturnType<typeof setTimeout> };
  const enCours = new Map<string, Groupe>();
  const cle = (w: JournalRollRow["roll"]["owner"]) => (w === null ? "?" : w.kind === "gm" ? "mj" : "pj:" + w.id);
  const clore = (place: string) => {
    const g = enCours.get(place); if (!g) return;
    enCours.delete(place);
    o.emettre({ action: "roll", roll: {
      atMs: Math.max(0, Math.round(g.premier - o.debutFluxMs)), owner: g.owner,
      dice: g.des, sum: g.des.reduce((s, d) => s + d.value, 0), source: "ble" } });
  };
  const offs = des.map((de) => de.surLancer((r: ResultatDe) => {
    const owner = o.proprietaire(de.nom), place = cle(owner);
    let g = enCours.get(place);
    if (!g) { g = { premier: r.horodatage, owner, des: [], minuterie: setTimeout(() => clore(place), fenetre) }; enCours.set(place, g); }
    g.des.push({ die: de.nom, faces: r.type, value: r.valeur });
  }));
  return () => { offs.forEach((off) => off()); [...enCours.keys()].forEach(clore); };
}

/** Validation côté serveur, dans l'esprit de lib/bard-live/validate.ts. */
export function isJournalRollRow(row: unknown): row is JournalRollRow {
  const o = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);
  const int = (x: unknown, max: number) => Number.isSafeInteger(x) && Number(x) >= 0 && Number(x) <= max;
  if (!o(row) || row.action !== "roll" || !o(row.roll)) return false;
  const r = row.roll;
  const w = r.owner;
  const ownerOk = w === null || (o(w) && (w.kind === "gm" || (w.kind === "character" && typeof w.id === "string" && w.id.length >= 1 && w.id.length <= 64)));
  return int(r.atMs, 11000000) && ownerOk &&
    Array.isArray(r.dice) && r.dice.length >= 1 && r.dice.length <= 10 &&
    r.dice.every((d) => o(d) && typeof d.die === "string" && d.die.length <= 32 && [4, 6, 8, 10, 12, 20].includes(Number(d.faces)) &&
      int(d.value, 20) && Number(d.value) >= 1 && Number(d.value) <= Number(d.faces)) &&
    int(r.sum, 200) && r.sum === (r.dice as { value: number }[]).reduce((s, d) => s + d.value, 0) &&
    (r.source === "ble" || r.source === "tablette");
}
