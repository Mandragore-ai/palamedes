/**
 * Module « mcdice » pour le Tabletop Kit de Mandragore (experiments/tabletop-kit).
 * Suit les règles du kit : désactivé par défaut, aucun accès DOM / réseau / stockage à l'import,
 * événements versionnés, désabonnement par fonction retournée.
 * Licence : CC BY-NC 4.0.
 */
import type { MCDice, ResultatDe } from "./mcdice";

export const MODULE_ID = "mcdice";
export const API_VERSION = 1;

export interface JetDe {
  apiVersion: 1;
  moduleId: typeof MODULE_ID;
  type: "dice.rolled";
  operationId: string;          // unique par jet : sert de clé d'idempotence côté serveur
  die: string;                  // nom annoncé du dé
  faces: number;
  value: number;
  confidence: number;
  source: "ble" | "tablette" | "plateau";
  rolledAt: string;             // ISO 8601, horloge de l'appareil
}

export interface ModuleDes {
  readonly id: typeof MODULE_ID;
  brancher(de: MCDice): () => void;   // renvoie la fonction de débranchement
  signalerTablette(d: { id: number; valeur: number; faces: number }): void;
  subscribe(f: (e: JetDe) => void): () => void;
  dispose(): void;
}

export function createDiceModule(opts: { enabled: boolean; now?: () => Date; uuid?: () => string }): ModuleDes | null {
  if (!opts.enabled) return null;
  const now = opts.now ?? (() => new Date());
  const uuid = opts.uuid ?? (() => crypto.randomUUID());
  const ecouteurs = new Set<(e: JetDe) => void>();
  const branches = new Set<() => void>();
  let actif = true;

  const emettre = (e: Omit<JetDe, "apiVersion" | "moduleId" | "type" | "operationId" | "rolledAt">) => {
    if (!actif) return;
    const jet: JetDe = { apiVersion: 1, moduleId: MODULE_ID, type: "dice.rolled", operationId: uuid(), rolledAt: now().toISOString(), ...e };
    ecouteurs.forEach((f) => f(jet));
  };

  return {
    id: MODULE_ID,
    brancher(de) {
      const off = de.surLancer((r: ResultatDe) =>
        emettre({ die: de.nom, faces: r.type, value: r.valeur, confidence: r.confiance, source: "ble" }));
      branches.add(off);
      return () => { off(); branches.delete(off); };
    },
    signalerTablette({ id, valeur, faces }) {
      emettre({ die: `id-${id}`, faces, value: valeur, confidence: 1, source: "tablette" });
    },
    subscribe(f) { ecouteurs.add(f); return () => ecouteurs.delete(f); },
    dispose() { actif = false; branches.forEach((off) => off()); branches.clear(); ecouteurs.clear(); },
  };
}
