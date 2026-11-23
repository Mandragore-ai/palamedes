/*
  Dé connecté Mandragore — firmware de départ (D-core v0.2, D20)
  Cible : module Fanstel BC832 (nRF52832), cœur Arduino « Adafruit nRF52 » (Bluefruit).
  ÉTAT : base de départ NON COMPILÉE ni testée sur le matériel — voir LISEZMOI_firmware.md.

  Fonctions :
   - lecture de l'accéléromètre LIS2DH12 (I2C 0x18), détection lancer -> arrêt -> face du haut
   - Bluetooth LE : service Mandragore (résultat + commandes) et service batterie standard
   - signal capacitif après chaque arrêt :
       mode ÉMISSION (plateau à l'encre) : trame Manchester sur le groupe de pastilles de la face posée
       mode TABLETTE : les 4 groupes « tapotent » (contact / pas de contact) pour coder l'identité et la valeur
   - mesure de la pile (pont diviseur sur AIN0) — pas de LED en v0.2
   - étalonnage en 2 poses (face 1 puis face 2) enregistré en mémoire flash
   - veille profonde (System OFF) après inactivité, réveil par mouvement (INT1 de l'accéléromètre)
*/
#include <bluefruit.h>
#include <Wire.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include "faces.h"

using namespace Adafruit_LittleFS_Namespace;

// ---------------------------------------------------------------- broches (P0.xx = numéro Arduino sur nRF52832)
#define PIN_SDA      26
#define PIN_SCL      27
#define PIN_ACC_INT  3
#define PIN_PILE     2    // AIN0 : pont 1 MΩ / 1 MΩ -> VBAT/2
#define PIN_CHRG     1    // TP4054 : bas = en charge
#define PIN_RX_SHORT 20   // Q1 (2N7002T) : haut = bobine court-circuitée (pile pleine sur le chargeur)
#define VBAT_PLEINE  4.15f  // au-dessus : on court-circuite la bobine (la zener ne chauffe plus)
#define VBAT_REPRISE 4.00f  // en dessous : on relâche, la charge reprend

#define ACC_ADDR     0x18
#define VEILLE_MS    (10UL * 60UL * 1000UL)   // System OFF après 10 min sans mouvement

// ---------------------------------------------------------------- Bluetooth
// service « mandragore » : 6d616e64-7261-676f-7265-0000000000xx
const uint8_t UUID_SVC[]  = {0x01,0,0,0,0,0,0x65,0x72,0x6f,0x67,0x61,0x72,0x64,0x6e,0x61,0x6d};
const uint8_t UUID_ROLL[] = {0x02,0,0,0,0,0,0x65,0x72,0x6f,0x67,0x61,0x72,0x64,0x6e,0x61,0x6d};
const uint8_t UUID_CMD[]  = {0x03,0,0,0,0,0,0x65,0x72,0x6f,0x67,0x61,0x72,0x64,0x6e,0x61,0x6d};
BLEService        svc(UUID_SVC);
BLECharacteristic chrRoll(UUID_ROLL);   // notify : [seq, état, valeur, face, confiance%, type]
BLECharacteristic chrCmd(UUID_CMD);     // write  : commandes (voir onCommande)
BLEBas            blebas;
BLEDfu            bledfu;                 // mise à jour Bluetooth « sans bouton » (nRF Connect / Device Manager)

enum Etat : uint8_t { REPOS = 0, ROULE = 1, ARRET = 2, PENCHE = 3 };
enum ModeCap : uint8_t { CAP_OFF = 0, CAP_EMISSION = 1, CAP_TABLETTE = 2, CAP_LES_DEUX = 3 };

struct Reglages {
  uint32_t magic = 0x4D44470A;
  float R[3][3] = {{1,0,0},{0,1,0},{0,0,1}};   // repère accéléromètre -> repère palet
  uint8_t id = 0;                              // identité du dé (0 = dérivée de l'adresse)
  uint8_t couleur[3] = {0, 40, 80};
  uint8_t modeCap = CAP_LES_DEUX;
} reglages;

uint8_t seq = 0;
Etat etat = REPOS;
uint32_t dernierMouvement = 0;
float calA[3];                     // première pose d'étalonnage

// ---------------------------------------------------------------- LIS2DH12
void accEcrire(uint8_t reg, uint8_t v) { Wire.beginTransmission(ACC_ADDR); Wire.write(reg); Wire.write(v); Wire.endTransmission(); }
uint8_t accLire(uint8_t reg) { Wire.beginTransmission(ACC_ADDR); Wire.write(reg); Wire.endTransmission(false); Wire.requestFrom(ACC_ADDR, 1); return Wire.read(); }

bool accInit() {
  if (accLire(0x0F) != 0x33) return false;   // WHO_AM_I
  accEcrire(0x20, 0x47);   // CTRL_REG1 : 50 Hz, X/Y/Z
  accEcrire(0x21, 0x01);   // CTRL_REG2 : filtre passe-haut sur INT1 (détection de mouvement)
  accEcrire(0x22, 0x40);   // CTRL_REG3 : IA1 -> INT1
  accEcrire(0x23, 0x88);   // CTRL_REG4 : BDU, ±2 g, haute résolution
  accEcrire(0x24, 0x08);   // CTRL_REG5 : INT1 verrouillée
  accEcrire(0x32, 0x06);   // INT1_THS : ≈ 96 mg
  accEcrire(0x33, 0x00);   // INT1_DURATION
  accEcrire(0x30, 0x2A);   // INT1_CFG : XH | YH | ZH
  accLire(0x31);           // efface INT1_SRC
  return true;
}

void accLireG(float a[3]) {
  Wire.beginTransmission(ACC_ADDR); Wire.write(0x28 | 0x80); Wire.endTransmission(false);
  Wire.requestFrom(ACC_ADDR, 6);
  for (int i = 0; i < 3; i++) { int16_t v = Wire.read() | (Wire.read() << 8); a[i] = v / 16384.0f; }
}

// ---------------------------------------------------------------- (v0.2 : pas de LED — fonctions vides gardées pour une future version translucide)
void led(uint8_t, uint8_t, uint8_t) {}
void ledEteinte() {}

// ---------------------------------------------------------------- géométrie
void versPalet(const float a[3], float u[3]) {
  for (int i = 0; i < 3; i++) u[i] = reglages.R[i][0]*a[0] + reglages.R[i][1]*a[1] + reglages.R[i][2]*a[2];
}
// u = direction « haut » dans le repère palet (normée). Renvoie la face du haut, la face posée et la confiance.
int faceDuHaut(const float u[3], int &faceBas, float &conf) {
  int best = 0, worst = 0; float bd = -2, wd = 2;
  for (int f = 0; f < NB_FACES; f++) {
    float d = FACES[f].nx*u[0] + FACES[f].ny*u[1] + FACES[f].nz*u[2];
    if (d > bd) { bd = d; best = f; }
    if (d < wd) { wd = d; worst = f; }
  }
  faceBas = worst; conf = bd;
  return best;
}

// ---------------------------------------------------------------- signal capacitif
void groupesHauteImpedance() { for (int g = 1; g <= 4; g++) pinMode(GROUPE_GPIO[g], INPUT); }

// ÉMISSION : trame [1010][id 8 bits][valeur 5 bits][somme 3 bits], Manchester 1 kbit/s, 3 répétitions.
// Pastilles du groupe actif pilotées en 0/3 V ; les autres groupes reliés à la masse du dé.
void emettre(uint8_t groupe, uint8_t valeur) {
  uint32_t trame = 0b1010;
  trame = (trame << 8) | reglages.id;
  trame = (trame << 5) | (valeur & 0x1F);
  trame = (trame << 3) | ((reglages.id + valeur) & 0x7);
  for (int g = 1; g <= 4; g++) { pinMode(GROUPE_GPIO[g], OUTPUT); digitalWrite(GROUPE_GPIO[g], LOW); }
  uint8_t p = GROUPE_GPIO[groupe];
  for (int rep = 0; rep < 3; rep++) {
    for (int b = 19; b >= 0; b--) {
      bool bit = (trame >> b) & 1;
      digitalWrite(p, bit ? HIGH : LOW); delayMicroseconds(500);
      digitalWrite(p, bit ? LOW : HIGH); delayMicroseconds(500);
    }
    digitalWrite(p, LOW); delay(5);
  }
  groupesHauteImpedance();
}

// TABLETTE : les 4 groupes ensemble ; contact = reliés à la masse du dé, rien = haute impédance.
// créneaux de 50 ms : départ (3 créneaux de contact + 1 vide) puis id (8 bits) et valeur (5 bits), 1 = contact.
void tapoter(uint8_t valeur) {
  auto contact = [](bool on) {
    for (int g = 1; g <= 4; g++) {
      if (on) { pinMode(GROUPE_GPIO[g], OUTPUT); digitalWrite(GROUPE_GPIO[g], LOW); }
      else pinMode(GROUPE_GPIO[g], INPUT);
    }
  };
  contact(true); delay(150); contact(false); delay(50);
  uint16_t mot = ((uint16_t)reglages.id << 5) | (valeur & 0x1F);
  for (int b = 12; b >= 0; b--) { contact((mot >> b) & 1); delay(50); }
  contact(false);
}

// ---------------------------------------------------------------- réglages en flash
void sauver() { InternalFS.remove("/reglages"); File f(InternalFS); if (f.open("/reglages", FILE_O_WRITE)) { f.write((uint8_t*)&reglages, sizeof(reglages)); f.close(); } }
void charger() {
  File f(InternalFS);
  if (f.open("/reglages", FILE_O_READ)) { Reglages r; if (f.read((uint8_t*)&r, sizeof(r)) == sizeof(r) && r.magic == reglages.magic) reglages = r; f.close(); }
  if (reglages.id == 0) reglages.id = (uint8_t)(NRF_FICR->DEVICEID[0] & 0xFF) | 1;
}

// étalonnage TRIAD : pose 1 = face de valeur 1 posée en haut ; pose 2 = face de valeur 2 en haut.
int faceDeValeur(uint8_t v) { for (int f = 0; f < NB_FACES; f++) if (FACES[f].valeur == v) return f; return 0; }
void triad(const float v1[3], const float v2[3], float M[3][3]) {   // base orthonormée (colonnes)
  float t1[3] = {v1[0], v1[1], v1[2]}; float n = sqrtf(t1[0]*t1[0]+t1[1]*t1[1]+t1[2]*t1[2]); for (auto &x : t1) x /= n;
  float t2[3] = {t1[1]*v2[2]-t1[2]*v2[1], t1[2]*v2[0]-t1[0]*v2[2], t1[0]*v2[1]-t1[1]*v2[0]};
  n = sqrtf(t2[0]*t2[0]+t2[1]*t2[1]+t2[2]*t2[2]); for (auto &x : t2) x /= n;
  float t3[3] = {t1[1]*t2[2]-t1[2]*t2[1], t1[2]*t2[0]-t1[0]*t2[2], t1[0]*t2[1]-t1[1]*t2[0]};
  for (int i = 0; i < 3; i++) { M[i][0] = t1[i]; M[i][1] = t2[i]; M[i][2] = t3[i]; }
}
void etalonner(uint8_t pose, const float a[3]) {
  if (pose == 1) { memcpy(calA, a, sizeof(calA)); led(0, 0, 120); return; }
  int f1 = faceDeValeur(1), f2 = faceDeValeur(2);
  float n1[3] = {FACES[f1].nx, FACES[f1].ny, FACES[f1].nz}, n2[3] = {FACES[f2].nx, FACES[f2].ny, FACES[f2].nz};
  float A[3][3], B[3][3];
  triad(calA, a, A);         // mesures (repère accéléromètre)
  triad(n1, n2, B);          // mêmes directions dans le repère palet
  for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) {   // R = B * A^T
    reglages.R[i][j] = 0; for (int k = 0; k < 3; k++) reglages.R[i][j] += B[i][k] * A[j][k];
  }
  sauver(); led(0, 120, 0); delay(400); ledEteinte();
}

// ---------------------------------------------------------------- commandes BLE
// 0x01 r g b : couleur | 0x02 n : pose d'étalonnage n (1 puis 2) | 0x03 m : mode capacitif | 0x04 id : identité
volatile uint8_t poseDemandee = 0;
void onCommande(uint16_t, BLECharacteristic*, uint8_t* d, uint16_t len) {
  if (len < 2) return;
  switch (d[0]) {
    case 0x01: if (len >= 4) { memcpy(reglages.couleur, d + 1, 3); sauver(); } break;
    case 0x02: poseDemandee = d[1]; break;
    case 0x03: reglages.modeCap = d[1] & 3; sauver(); break;
    case 0x04: reglages.id = d[1]; sauver(); break;
  }
}

void publier(Etat e, uint8_t valeur, uint8_t face, float conf) {
  uint8_t p[6] = { ++seq, (uint8_t)e, valeur, face, (uint8_t)(constrain(conf, 0, 1) * 100), 20 };
  chrRoll.write(p, sizeof(p));
  if (Bluefruit.connected()) chrRoll.notify(p, sizeof(p));
}

// niveau de pile : VBAT = 2 × tension sur AIN0 ; courbe Li-ion simplifiée 3,3 V (0 %) -> 4,15 V (100 %)
float tensionPile() {
  analogReference(AR_INTERNAL);            // 0,6 V × 6 = 3,6 V pleine échelle
  analogReadResolution(12);
  analogSampleTime(40);                    // source 500 kΩ : acquisition de 40 µs
  uint32_t s = 0; for (int i = 0; i < 8; i++) s += analogRead(PIN_PILE);
  return (s / 8.0f) * 3.6f / 4096.0f * 2.0f;
}
// pile pleine sur le chargeur : court-circuiter la bobine (cf. sim_wpt_rlim.py, zener jusqu'à 381 mW sinon).
// Le chargeur voit toujours le dé (courant d'émission différent du vide) et coupe sur minuterie.
// L'état de la broche est conservé en System OFF : un dé qui s'endort plein sur le chargeur reste court-circuité.
bool bobineCourtCircuitee = false;
void gererCourtCircuit(float v) {
  if (!bobineCourtCircuitee && v >= VBAT_PLEINE) bobineCourtCircuitee = true;
  else if (bobineCourtCircuitee && v <= VBAT_REPRISE) bobineCourtCircuitee = false;
  digitalWrite(PIN_RX_SHORT, bobineCourtCircuitee ? HIGH : LOW);
}
uint8_t niveauPile() {
  float v = tensionPile();
  return (uint8_t)constrain((v - 3.3f) / (4.15f - 3.3f) * 100.0f, 0.0f, 100.0f);
}

// ---------------------------------------------------------------- démarrage
void setup() {
  pinMode(PIN_RX_SHORT, OUTPUT); digitalWrite(PIN_RX_SHORT, LOW);   // R4 100 kΩ tient la grille à la masse au repos
  pinMode(PIN_CHRG, INPUT_PULLUP);
  pinMode(PIN_ACC_INT, INPUT);
  groupesHauteImpedance();
  InternalFS.begin(); charger();
  Wire.setPins(PIN_SDA, PIN_SCL); Wire.begin(); Wire.setClock(400000);
  if (!accInit()) { for (int i = 0; i < 6; i++) { led(150, 0, 0); delay(150); ledEteinte(); delay(150); } }

  Bluefruit.begin();
  Bluefruit.setTxPower(0);
  char nom[16]; snprintf(nom, sizeof(nom), "PAL-D20-%02X", reglages.id); Bluefruit.setName(nom);
  bledfu.begin();                                  // à déclarer en premier : indispensable une fois le dé coulé dans la résine
  svc.begin();
  chrRoll.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY); chrRoll.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  chrRoll.setFixedLen(6); chrRoll.begin();
  chrCmd.setProperties(CHR_PROPS_WRITE | CHR_PROPS_WRITE_WO_RESP); chrCmd.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
  chrCmd.setMaxLen(8); chrCmd.setWriteCallback(onCommande); chrCmd.begin();
  gererCourtCircuit(tensionPile());
  blebas.begin(); blebas.write(niveauPile());

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addService(svc);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(160, 800);     // 100 ms -> 500 ms
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  led(reglages.couleur[0], reglages.couleur[1], reglages.couleur[2]); delay(300); ledEteinte();
  dernierMouvement = millis();
}

// ---------------------------------------------------------------- boucle : 50 Hz
void loop() {
  static float prec[3] = {0, 0, 1};
  static uint16_t calme = 0;
  float a[3]; accLireG(a);
  float n = sqrtf(a[0]*a[0] + a[1]*a[1] + a[2]*a[2]);
  float delta = fabsf(a[0]-prec[0]) + fabsf(a[1]-prec[1]) + fabsf(a[2]-prec[2]);
  memcpy(prec, a, sizeof(prec));

  bool bouge = delta > 0.08f || fabsf(n - 1.0f) > 0.15f;
  if (bouge) {
    calme = 0; dernierMouvement = millis();
    if (etat != ROULE) { etat = ROULE; publier(ROULE, 0, 0, 0); }
  } else if (calme < 1000) calme++;

  if (etat == ROULE && calme == 25) {            // 0,5 s immobile -> résultat
    float an[3] = {a[0]/n, a[1]/n, a[2]/n}, u[3]; versPalet(an, u);
    int bas; float conf; int f = faceDuHaut(u, bas, conf);
    if (conf > 0.93f) {
      etat = ARRET; publier(ARRET, FACES[f].valeur, f, conf);
      led(reglages.couleur[0], reglages.couleur[1], reglages.couleur[2]);
      if (reglages.modeCap & CAP_EMISSION) emettre(FACES[bas].groupe, FACES[f].valeur);
      if (reglages.modeCap & CAP_TABLETTE) tapoter(FACES[f].valeur);
      ledEteinte();
    } else { etat = PENCHE; publier(PENCHE, 0, f, conf); }   // dé « cassé » (penché)
    blebas.write(niveauPile());
  }

  static uint32_t dernierControlePile = 0;
  if (millis() - dernierControlePile > 5000) { dernierControlePile = millis(); gererCourtCircuit(tensionPile()); }

  if (poseDemandee && calme > 25) { float an[3] = {a[0]/n, a[1]/n, a[2]/n}; etalonner(poseDemandee, an); poseDemandee = 0; }


  if (millis() - dernierMouvement > VEILLE_MS && !Bluefruit.connected() && digitalRead(PIN_CHRG) == HIGH) {
    ledEteinte(); groupesHauteImpedance(); accLire(0x31);       // réarme l'interruption de mouvement
    systemOff(PIN_ACC_INT, HIGH);                                // réveil au prochain mouvement (redémarrage)
  }
  delay(20);
}
