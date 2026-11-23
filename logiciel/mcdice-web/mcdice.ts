/**
 * MCDice — client Web Bluetooth pour Mandragore (Next.js : à importer dans un composant « use client »).
 * Aucune dépendance. Navigateurs : Chrome / Edge (ordinateur, Android). Pas Safari iOS (pas de Web Bluetooth).
 * Licence : CC BY-NC 4.0 (voir LICENSE.md du dépôt MCDice).
 *
 * Usage :
 *   const de = await MCDice.connecter();            // ouvre le sélecteur de périphériques (geste utilisateur requis)
 *   de.surLancer((r) => console.log(r.valeur));     // chaque résultat stable
 *   await de.definirIdentite(7);
 */

export const MCDICE_SERVICE = "6d616e64-7261-676f-7265-000000000001";
export const MCDICE_RESULTAT = "6d616e64-7261-676f-7265-000000000002";
export const MCDICE_COMMANDE = "6d616e64-7261-676f-7265-000000000003";

export type EtatDe = "repos" | "roule" | "arrete" | "penche";
const ETATS: EtatDe[] = ["repos", "roule", "arrete", "penche"];

export interface ResultatDe {
  sequence: number;      // 0-255, incrémenté à chaque message (sert à ignorer les doublons)
  etat: EtatDe;          // « arrete » = valeur valide ; « penche » = dé cassé, à relancer
  valeur: number;        // 1..N si etat = arrete, sinon 0
  face: number;          // indice interne de face (0..N-1)
  confiance: number;     // 0..1
  type: number;          // nombre de faces du dé (4, 6, 8, 10, 12, 20)
  horodatage: number;    // performance.now() à la réception
}

export type ModeCapacitif = "coupe" | "plateau" | "tablette" | "les-deux";
const MODES: Record<ModeCapacitif, number> = { coupe: 0, plateau: 1, tablette: 2, "les-deux": 3 };

export function decoderResultat(v: DataView): ResultatDe {
  if (v.byteLength < 6) throw new Error(`trame MCDice trop courte (${v.byteLength} octets)`);
  return {
    sequence: v.getUint8(0), etat: ETATS[v.getUint8(1)] ?? "repos", valeur: v.getUint8(2), face: v.getUint8(3),
    confiance: v.getUint8(4) / 100, type: v.getUint8(5), horodatage: performance.now(),
  };
}

export class MCDice {
  private ecouteurs = new Set<(r: ResultatDe) => void>();
  private ecouteursDeconnexion = new Set<() => void>();
  private derniereSequence = -1;

  private constructor(readonly appareil: BluetoothDevice, private resultat: BluetoothRemoteGATTCharacteristic,
                      private commande: BluetoothRemoteGATTCharacteristic, private batterie?: BluetoothRemoteGATTCharacteristic) {}

  /** Nom annoncé par le dé, ex. « PAL-D20-07 ». */
  get nom(): string { return this.appareil.name ?? "MCDice"; }

  static disponible(): boolean { return typeof navigator !== "undefined" && "bluetooth" in navigator; }

  /** Ouvre le sélecteur du navigateur (doit être appelé depuis un clic) et se connecte au dé choisi. */
  static async connecter(): Promise<MCDice> {
    if (!MCDice.disponible()) throw new Error("Web Bluetooth indisponible (Chrome ou Edge requis)");
    const appareil = await navigator.bluetooth.requestDevice({
      filters: [{ services: [MCDICE_SERVICE] }], optionalServices: ["battery_service"],
    });
    return MCDice.ouvrir(appareil);
  }

  /** Reconnexion à un dé déjà autorisé (navigator.bluetooth.getDevices, si le navigateur le permet). */
  static async ouvrir(appareil: BluetoothDevice): Promise<MCDice> {
    const gatt = await appareil.gatt!.connect();
    const svc = await gatt.getPrimaryService(MCDICE_SERVICE);
    const res = await svc.getCharacteristic(MCDICE_RESULTAT);
    const cmd = await svc.getCharacteristic(MCDICE_COMMANDE);
    let bat: BluetoothRemoteGATTCharacteristic | undefined;
    try { bat = await (await gatt.getPrimaryService("battery_service")).getCharacteristic("battery_level"); } catch { /* facultatif */ }
    const de = new MCDice(appareil, res, cmd, bat);
    res.addEventListener("characteristicvaluechanged", (e) => de.recevoir((e.target as BluetoothRemoteGATTCharacteristic).value!));
    await res.startNotifications();
    appareil.addEventListener("gattserverdisconnected", () => de.ecouteursDeconnexion.forEach((f) => f()));
    return de;
  }

  private recevoir(v: DataView) {
    const r = decoderResultat(v);
    if (r.sequence === this.derniereSequence) return;
    this.derniereSequence = r.sequence;
    this.ecouteurs.forEach((f) => f(r));
  }

  /** Tous les messages (roule, arrêté, penché). Renvoie une fonction de désabonnement. */
  surMessage(f: (r: ResultatDe) => void): () => void { this.ecouteurs.add(f); return () => this.ecouteurs.delete(f); }
  /** Uniquement les résultats valides (dé arrêté sur une face). */
  surLancer(f: (r: ResultatDe) => void): () => void { return this.surMessage((r) => { if (r.etat === "arrete") f(r); }); }
  surDeconnexion(f: () => void): () => void { this.ecouteursDeconnexion.add(f); return () => this.ecouteursDeconnexion.delete(f); }

  async lireDernier(): Promise<ResultatDe> { return decoderResultat(await this.resultat.readValue()); }
  async niveauPile(): Promise<number | undefined> { return this.batterie ? (await this.batterie.readValue()).getUint8(0) : undefined; }

  private envoyer(octets: number[]) { return this.commande.writeValueWithResponse(new Uint8Array(octets)); }
  /** Identité 0..255 (transmise aussi par le signal capacitif). */
  definirIdentite(id: number) { return this.envoyer([0x04, id & 0xff]); }
  definirModeCapacitif(m: ModeCapacitif) { return this.envoyer([0x03, MODES[m]]); }
  /** Étalonnage en deux poses : face 1 en haut puis face 2 en haut. */
  etalonner(pose: 1 | 2) { return this.envoyer([0x02, pose]); }
  /** Couleur du joueur (réservé à une future version avec voyant). */
  definirCouleur(r: number, g: number, b: number) { return this.envoyer([0x01, r, g, b]); }

  deconnecter() { this.appareil.gatt?.disconnect(); }
}

/**
 * Décodage du « tapotement » capacitif sur tablette (mode tablette du dé) : à brancher sur les événements
 * pointerdown / pointerup d'une zone de l'écran. Créneaux de 50 ms : départ = 150 ms de contact + 50 ms sans,
 * puis 13 bits (identité 8 bits, valeur 5 bits), bit 1 = contact.
 */
export class DecodeurTapotement {
  private fronts: [number, 0 | 1, number, number][] = [];
  private minuterie?: ReturnType<typeof setTimeout>;
  constructor(private surDe: (d: { id: number; valeur: number; x: number; y: number }) => void, private creneauMs = 50) {}

  pointeur(etat: 0 | 1, x: number, y: number, t = performance.now()) {
    this.fronts.push([t, etat, x, y]);
    clearTimeout(this.minuterie);
    this.minuterie = setTimeout(() => this.decoder(), this.creneauMs * 20);
  }

  private decoder() {
    const f = this.fronts; this.fronts = [];
    if (f.length < 2 || f[0][1] !== 1) return;
    const t0 = f[0][0], debut = t0 + 4 * this.creneauMs, bits: number[] = [];
    const etatA = (t: number) => { let e = 0; for (const [tt, s] of f) { if (tt <= t) e = s; else break; } return e; };
    for (let k = 0; k < 13; k++) bits.push(etatA(debut + (k + 0.5) * this.creneauMs));
    const mot = bits.reduce((a, b) => (a << 1) | b, 0);
    this.surDe({ id: mot >> 5, valeur: mot & 31, x: f[0][2], y: f[0][3] });
  }
}
