/*
  MCDice — firmware de la boîte-chargeur 7 emplacements (CH32V203C8T6)
  Cœur Arduino : « CH32 MCU EVT Boards » (openwch/arduino_core_ch32), carte « CH32V20x_EVT », variante CH32V203C8T6.
  Licence : CC BY-NC 4.0 (voir LICENSE.md du dépôt).

  Principe
  - Un demi-pont commun (AO3401A / AO3400A via UCC27524) produit un carré 0-5 V à 1 MHz sur le bus SW.
  - Chaque emplacement est un circuit série : 12,2 nF C0G -> spirale (≈2,0 µH) -> AO3400A (EN) -> 1,1 Ω -> masse.
  - Un détecteur de crête (B5819W + 100 nF + 100 kΩ) sur la résistance donne une image du courant -> ADC.
  - Emplacement vide : circuit accordé sans charge, courant fort (≈0,97 A eff, simulé) -> crête haute -> on coupe.
  - Dé posé : la bobine du dé absorbe l'énergie, courant 0,19 à 0,45 A eff (simulé) -> crête basse -> on charge.
  - Chaque emplacement « sonde » 3 ms par seconde ; en charge, contrôle toutes les 100 ms ; arrêt au bout de 4 h.
    (Le dé coupe lui-même sa réception quand sa pile est pleine ; la minuterie évite de chauffer pour rien.)

  Commande du demi-pont (TIM1, sorties complémentaires avec temps mort) :
    PA8  = TIM1_CH1  -> INA -> OUTA -> grille du P (haut = P bloqué)  : polarité inversée (CC1P = 1)
    PB13 = TIM1_CH1N -> INB -> OUTB -> grille du N (haut = N passant) : polarité normale (CC1NP = 0)
    Avec ces polarités, INA monte avant INB et INB redescend avant INA : jamais les deux transistors passants.
    Sorties désactivées (MOE = 0) : R3 tire INA haut et R4 tire INB bas -> les deux transistors bloqués.

  À valider sur le premier prototype : le seuil SEUIL_VIDE_V (lire les valeurs sur le port série),
  (PB4 : le CH32V203 n'a qu'un débogage 2 fils, PB4 est une E/S ordinaire).
*/
#include <Arduino.h>

#define F_HZ          1000000UL   // fréquence d'émission (résonance de la spirale + 12,2 nF)
#define DEADTIME_DTG  7           // ≈ 49 ns à 144 MHz
#define SEUIL_VIDE_V  0.85f       // crête au-dessus : emplacement vide (à ajuster au premier essai)
#define SONDE_MS      3
#define PERIODE_SONDE 1000UL
#define DUREE_CHARGE  (4UL * 3600UL * 1000UL)
#define PIN_LED       PB11

const uint8_t NB = 7;
const uint32_t PIN_EN[NB] = {PC13, PC14, PA5, PA4, PB4, PB10, PA7};
const uint32_t PIN_PK[NB] = {PA0, PA1, PA2, PA3, PB1, PB0, PA6};
const char* NOM[NB] = {"D4", "D6", "D8", "D10", "D%", "D12", "D20"};

enum Etat : uint8_t { VIDE, CHARGE, FINI };
Etat etat[NB];
uint32_t debut[NB], derniereSonde[NB];
uint8_t alertes[NB];
float derniereCrete[NB];

// ------------------------------------------------------------------ demi-pont
void demiPontInit() {
  GPIO_InitTypeDef g = {0};
  RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB | RCC_APB2Periph_TIM1 | RCC_APB2Periph_AFIO, ENABLE);
  g.GPIO_Mode = GPIO_Mode_AF_PP; g.GPIO_Speed = GPIO_Speed_50MHz;
  g.GPIO_Pin = GPIO_Pin_8;  GPIO_Init(GPIOA, &g);
  g.GPIO_Pin = GPIO_Pin_13; GPIO_Init(GPIOB, &g);

  TIM_TimeBaseInitTypeDef tb = {0};
  uint16_t arr = (uint16_t)(SystemCoreClock / F_HZ - 1);
  tb.TIM_Period = arr; tb.TIM_Prescaler = 0; tb.TIM_ClockDivision = TIM_CKD_DIV1;
  tb.TIM_CounterMode = TIM_CounterMode_Up; tb.TIM_RepetitionCounter = 0;
  TIM_TimeBaseInit(TIM1, &tb);

  TIM_OCInitTypeDef oc = {0};
  oc.TIM_OCMode = TIM_OCMode_PWM1;
  oc.TIM_OutputState = TIM_OutputState_Enable; oc.TIM_OutputNState = TIM_OutputNState_Enable;
  oc.TIM_Pulse = (arr + 1) / 2;
  oc.TIM_OCPolarity = TIM_OCPolarity_Low;      // CC1P = 1
  oc.TIM_OCNPolarity = TIM_OCNPolarity_High;   // CC1NP = 0
  oc.TIM_OCIdleState = TIM_OCIdleState_Set; oc.TIM_OCNIdleState = TIM_OCNIdleState_Reset;
  TIM_OC1Init(TIM1, &oc);
  TIM_OC1PreloadConfig(TIM1, TIM_OCPreload_Enable);

  TIM_BDTRInitTypeDef bd = {0};
  bd.TIM_OSSRState = TIM_OSSRState_Disable; bd.TIM_OSSIState = TIM_OSSIState_Disable;   // MOE = 0 -> sorties libres
  bd.TIM_LOCKLevel = TIM_LOCKLevel_OFF; bd.TIM_DeadTime = DEADTIME_DTG;
  bd.TIM_Break = TIM_Break_Disable; bd.TIM_AutomaticOutput = TIM_AutomaticOutput_Disable;
  TIM_BDTRConfig(TIM1, &bd);
  TIM_ARRPreloadConfig(TIM1, ENABLE);
  TIM_Cmd(TIM1, ENABLE);
}
bool pontActif = false;
void pont(bool on) {
  if (on == pontActif) return;
  TIM_CtrlPWMOutputs(TIM1, on ? ENABLE : DISABLE);
  pontActif = on;
}
bool en[NB];
void activer(uint8_t k, bool on) {           // met l'emplacement en service, puis ajuste le demi-pont
  digitalWrite(PIN_EN[k], on ? HIGH : LOW); en[k] = on;
  bool besoin = false;
  for (uint8_t i = 0; i < NB; i++) besoin |= en[i];
  pont(besoin);
}

// ------------------------------------------------------------------ mesures
float crete(uint8_t k) {
  uint32_t s = 0;
  for (int i = 0; i < 8; i++) s += analogRead(PIN_PK[k]);
  return s / 8.0f * 3.3f / 4095.0f;
}
float sonder(uint8_t k) {
  activer(k, true);
  delay(SONDE_MS);
  float v = crete(k);
  activer(k, false);
  return v;
}

// ------------------------------------------------------------------ programme
void setup() {
  for (uint8_t k = 0; k < NB; k++) { pinMode(PIN_EN[k], OUTPUT); digitalWrite(PIN_EN[k], LOW); etat[k] = VIDE; }
  pinMode(PIN_LED, OUTPUT); digitalWrite(PIN_LED, LOW);
  analogReadResolution(12);
  Serial.begin(115200);
  demiPontInit(); pont(false);
  Serial.println("MCDice chargeur pret");
}

void loop() {
  uint32_t t = millis();
  for (uint8_t k = 0; k < NB; k++) {
    switch (etat[k]) {
      case VIDE:
      case FINI:
        if (t - derniereSonde[k] >= (etat[k] == VIDE ? PERIODE_SONDE : 10 * PERIODE_SONDE)) {
          derniereSonde[k] = t;
          float v = sonder(k); derniereCrete[k] = v;
          bool present = v < SEUIL_VIDE_V;
          if (etat[k] == VIDE && present) {
            etat[k] = CHARGE; debut[k] = t; alertes[k] = 0;
            activer(k, true);
            Serial.print(NOM[k]); Serial.print(" : de pose, charge (crete "); Serial.print(v, 2); Serial.println(" V)");
          } else if (etat[k] == FINI && !present) {
            etat[k] = VIDE;
            Serial.print(NOM[k]); Serial.println(" : de retire");
          }
        }
        break;
      case CHARGE:
        if (t - derniereSonde[k] >= 100) {
          derniereSonde[k] = t;
          float v = crete(k); derniereCrete[k] = v;
          alertes[k] = (v >= SEUIL_VIDE_V) ? alertes[k] + 1 : 0;
          if (alertes[k] >= 3) {                      // dé retiré
            etat[k] = VIDE; activer(k, false);
            Serial.print(NOM[k]); Serial.println(" : de retire");
          } else if (t - debut[k] >= DUREE_CHARGE) {   // fin de minuterie
            etat[k] = FINI; activer(k, false);
            Serial.print(NOM[k]); Serial.println(" : charge terminee");
          }
        }
        break;
    }
  }
  // voyant : clignote si au moins un dé charge, fixe si des charges sont terminées, éteint sinon
  bool charge = false, fini = false;
  for (uint8_t k = 0; k < NB; k++) { charge |= etat[k] == CHARGE; fini |= etat[k] == FINI; }
  digitalWrite(PIN_LED, charge ? ((t / 500) & 1) : (fini ? HIGH : LOW));

  static uint32_t dernierRapport = 0;
  if (t - dernierRapport > 5000) {
    dernierRapport = t;
    for (uint8_t k = 0; k < NB; k++) {
      Serial.print(NOM[k]); Serial.print('='); Serial.print(etat[k] == VIDE ? "vide" : etat[k] == CHARGE ? "charge" : "fini");
      Serial.print('('); Serial.print(derniereCrete[k], 2); Serial.print(") ");
    }
    Serial.println();
  }
}
