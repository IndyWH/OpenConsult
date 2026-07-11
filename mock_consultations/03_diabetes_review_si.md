# 03 — Diabetes and blood-pressure review (Sinhala / English code-switched)

**Fictional patient:** Mrs. Kamala Fernando, 58, retired teacher, type 2 diabetes for 8 years
**Speakers:** Doctor, Patient · **Target length:** 4–5 minutes
**Language:** Sri Lankan spoken Sinhala with embedded English medical/loan terms
("sugar eka", "pressure", drug names, test names). Patient speaks mostly Sinhala;
the doctor mixes both. This is the **dense-vocabulary** case — drug names, doses
and investigations are exactly the English tokens the ASR must not lose.

## Which evaluation this serves

- **Primary — Phase 5 Sinhala ASR recordings evaluation** (pre-registered in
  `evals/2026-07-10_sinhala_asr_benchmark.md`, § Pre-registration). The heaviest
  **code-switching** case in the set: `gliclazide`, `metformin`, `atorvastatin`,
  `losartan`, `HbA1c`, `monofilament` are the per-script-class /
  English-term-recall targets. As-spoken Sinhala turns are the source for
  `recordings/refs/03_diabetes_review_si.txt`.
- **Secondary** — with Sinhala ASR + translation in place, exercises the CDS /
  notes pipeline against the same **Expected clinical content** marking scheme as
  `03_diabetes_review_en.md` (clinical content identical). Note: the English
  script-03 note also carries the deliberate fidelity specimens tracked in the
  end-of-project docket (invented "atorvastatin 1 mg", inverted monofilament
  finding); if this Sinhala version is ever used for a note-fidelity check,
  keep the *spoken* facts here truthful so the audit compares like with like.

## Expected clinical content (marking scheme for AI outputs)

Identical to `03_diabetes_review_en.md`:

- **Problems:** type 2 diabetes with suboptimal control, hypertension, new peripheral neuropathy symptoms, overdue eye screening, statin not yet started
- **Current medication:** metformin 1 g twice daily, gliclazide 80 mg in the morning, losartan 50 mg daily
- **Key positives:** HbA1c 8.4% three months ago, home fasting sugars around 160, burning/tingling in both feet at night for ~2 months, increased thirst, sweet tea twice daily, large rice portions, no regular exercise
- **Key negatives:** no chest pain, no visual complaints, no foot ulcers, no hypoglycaemic episodes
- **Examination:** BP 140/85, weight 68 kg, feet — skin intact, pulses present, reduced monofilament sensation both forefeet
- **Plan:** increase gliclazide to 80 mg twice daily, start atorvastatin at night, repeat HbA1c, creatinine/eGFR, lipid profile, urine ACR, refer for retinal (eye) screening, daily foot inspection advice, dietary changes (smaller rice portion, stop sugar in tea, evening walking), review in 3 months with results

## English-term list (for the code-switching metric)

Freeze before viewing any hypothesis.

**Clinically load-bearing English terms present in the as-spoken reference:**

`diabetes`, `metformin`, `gliclazide`, `losartan`, `atorvastatin`, `HbA1c`,
`cholesterol`, `neuropathy`, `monofilament`, `sugar` (glucose control),
`pressure` / `blood pressure`, `kidney test`, `urine test`, `eye screening`,
`chest pain`. Doses/readings (digit class): `160`, `170`, `8.4`, `140/85`, `68`,
`80`, `50`, `7`.

**Other English / loan tokens present (context):**
`check-up`, `control`, `test`, `tablet`, `machine`, `average`, `normal`,
`plate`, `tea`, `sugar`, `string hoppers`, `exercise`, `standard`, `visit`,
`referral`, `photo`, `promise`, `results`, `Mrs`, `Fernando`.

**Scoring notes (from the pre-registration):**
- *Strict script matching:* a Sinhala transliteration (e.g. `gliclazide` →
  `ග්ලික්ලසයිඩ්`, `HbA1c` → `එච්බීඒවන්සී`) is a **mechanical miss**; the manual
  adjudication pass records transliterated hits separately. Drug names are where
  transliteration is most likely and where a mechanical miss matters most —
  read them clearly as English when recording.
- Doses are load-bearing: "gliclazide **80** morning and **80** night" and
  "atorvastatin **one** at night" must survive; a lost or altered number is a
  patient-safety error, not just an ASR error.

---

## Consultation — as spoken (reference transcript)

**DOCTOR:** Good morning, Mrs. Fernando. වාඩි වෙන්න. diabetes check-up එකට නේද ආවෙ?

**PATIENT:** ඔව්, දොස්තර. ගිය වතාවෙ ඉඳන් මාස තුනක් වුණා.

**DOCTOR:** සාමාන්‍යයෙන් කොහොමද ඉන්නෙ?

**PATIENT:** නරකම නෑ, දොස්තර. ඒත් මේ දවස්වල ගොඩක් thirst එකයි — වතුර බොන්න හිතෙනවා. ඊට අමතරව එක දෙයක් කරදරයි — මගේ කකුල්. රෑට, දෙ පැත්තෙම, පිච්චෙනවා වගේ, කූඩැල්ලො යනවා වගේ tingling එකක්. සමහර වෙලාවට නින්දෙන් ඇහැරෙනවා.

**DOCTOR:** මේක කොච්චර කාලෙක ඉඳන්ද?

**PATIENT:** මාස දෙකක් විතර ඇති දැන්.

**DOCTOR:** දෙ කකුලෙම එකවගේද? හිරි වැටෙනවා වගේ — කොට්ට උඩ ඇවිදිනවා වගේ දැනෙනවද? කකුල්වල තුවාලයක්, ulcer එකක් තියෙනවද?

**PATIENT:** දෙ කකුලෙම, ඔව්. ටිකක් හිරි වගේත් තියෙනවා. තුවාල නෑ — මම බලනවා, දුව කිව්වා බලන්න කියලා.

**DOCTOR:** ඔයා බලනවා කියන එක ගොඩක් හොඳයි. දැන්, sugar control එක. ඔයා metformin එක උදේට එකයි රෑට එකයි — gram එක බැගින් — gliclazide 80 උදේට, තාම එහෙමද ගන්නෙ?

**PATIENT:** ඔව් දොස්තර, මම මගහරින්නෙ නෑ. pressure එකට losartan 50 එකත් තියෙනවා.

**DOCTOR:** sugar අඩු වෙන episode — වෙව්ලනවා, දාඩිය දානවා, ක්ලාන්ත වගේ — එහෙම වෙලා තියෙනවද?

**PATIENT:** නෑ, එහෙම මුකුත් නෑ.

**DOCTOR:** ගෙදරදි sugar එක බලනවද?

**PATIENT:** පුතා machine එකක් අරන් දුන්නා. උදේ, කන්න කලින් sugar එක සාමාන්‍යයෙන් 160 විතර. සමහර දාට 170.

**DOCTOR:** ඔයාගෙ අන්තිම HbA1c එක — මාස තුනේ average එක පෙන්නන test එක — 8.4. අපිට ඕන 7ට වඩා අඩුවෙන්. ඉතින් fasting readings සහ HbA1c එක දෙකම කියන්නෙ එකම කතාව — control එක තියෙන්න ඕන තැන නෑ. කෑම ගැන කියන්න. ඇත්ත කියන්න දැන්!

**PATIENT:** *(හිනා වෙනවා)* දොස්තර, මම normal විදිහට කනවා. දවල්ට bath, රෑට පාන් නැත්නම් string hoppers.

**DOCTOR:** කොච්චර bath ද? අතින් පෙන්නන්න.

**PATIENT:** ...හොඳ plate එකක්, දොස්තර. tea එකට sugar — හැඳි දෙකක්, දවසට දෙ පාරක්. දන්නවා, දන්නවා.

**DOCTOR:** *(හිනා වෙනවා)* මම කියන්න කලින් ඔයා කිව්වා. exercise එකක් — ඇවිදිනවද?

**PATIENT:** එහෙම නෑ. මගේ දණ, දොස්තර.

**DOCTOR:** chest pain, ඇවිදින කොට හුස්ම වැටෙනවද? ඇස්වල අවුලක් — බොඳ වෙනවා වගේ?

**PATIENT:** chest pain නෑ. ඇස් හොඳයි, ඒත් eye check එක කරලා අවුරුද්දකට වඩා වෙනවා.

**DOCTOR:** ඒක අපි අද හදමු. දැන් මම examine කරන්නම්. මුලින්ම blood pressure එක... 140 over 85. ගිය සැරෙට වඩා හොඳයි, ඒත් diabetes එක්ක මම කැමතියි ටිකක් අඩුවෙන් තියෙනවට. බර... kilo 68, කලින් වගේම. දැන් කකුල් — සපත්තු, මේස් ගලවන්න. හම හොඳට තියෙනවා, පැලුම් නෑ, ulcer නෑ. pulses... දෙ කකුලෙම දැනෙනවා, හොඳයි. දැන් ඇස් වහගන්න — මේ හීන් monofilament එක ඇඟිලිවලට තට්ටු කරන කොට කියන්න... මෙතන?... මෙතන?... මෙතනද?

**PATIENT:** ...වළලුකර එක දැනුනා. ඇඟිලිවල ඒව නම් හරියට දැනුනෙ නෑ, දොස්තර.

**DOCTOR:** මම හිතුවෙ ඒකමයි. Mrs. Fernando, මේ පිච්චීම සහ අඩු වෙච්ච හැඟීම — මේක diabetic nerve damage, neuropathy එකක්. අවුරුදු ගාණක් sugar එක වැඩියෙන් තිබ්බම වෙන දෙයක්. ශරීරෙ අපිට කියනවා control එක තද කරන්න කියලා, දැන්, තව නරක වෙන්න කලින්.

**PATIENT:** මේක සනීප වෙනවද, දොස්තර?

**DOCTOR:** වෙච්ච damage එක ආපහු හදන්න අමාරුයි, ඒත් හොඳ control එකෙන් තව ඉස්සරහට යන එක නවතිනවා, පිච්චීමත් බොහෝ විට අඩු වෙනවා. ඒ නිසා අද අපි වෙනස්කම් ටිකක් කරමු. එක — gliclazide එක උදේට 80යි රෑට 80යි කරනවා. metformin එක එහෙමම. දෙක — cholesterol tablet එකක්, atorvastatin, රෑට එකක්, පටන් ගන්නවා. diabetes එක්ක අපි හදවත කලින්ම ආරක්ෂා කරනවා; මේක standard, අලුත් අවුලක් නිසා නෙවෙයි.

**PATIENT:** හරි, දොස්තර.

**DOCTOR:** තුන — ඊළඟ visit එකට කලින් test ටිකක්: HbA1c, kidney test එක, cholesterol, සහ protein බලන්න urine test එකක් — ඒකෙන් බලනවා diabetes එක kidney වලට බලපානවද කියලා. හතර — eye screening එක. මම දැන්ම referral එක ලියනවා; එයාල ඇහේ පිටිපස්සෙ photo ගන්නවා. අවුරුද්දකට වඩා diabetes එක්ක වැඩියි.

**PATIENT:** මම යනවා, දොස්තර.

**DOCTOR:** කෑම. bath එක දැන් ගන්න ප්‍රමාණයෙන් බාගයට අඩු කරන්න — ඉතුරු ඉඩ එළවළු, ගොටුකොළ, මැල්ලුම්, පරිප්පු වලින් පුරවන්න. tea එකේ sugar — සම්පූර්ණයෙන්ම නවත්තන්න. ඒක විතරක් දවසට හතර පාරක් හැඳි ගාණක් sugar කෙලින්ම ලේට දාන එකක්. ඇවිදීම — දණ එක්ක, පොඩ්ඩෙන් පටන් ගන්න: හවසට විනාඩි පහළොවක්, පැතලි පාරෙ, හරි සපත්තු දාලා.

**PATIENT:** sugar නැතුවම බොන්නද, දොස්තර? plain tea නම් ගොඩක් සෝකයි.

**DOCTOR:** *(හිනා වෙනවා)* සති දෙකකින් පුරුදු වෙනවා, promise. ඔයාගෙ කකුල්: හැම දවසෙම බලන්න, දුව කිව්ව වගේ — උඩ, යට, ඇඟිලි අතර. මොකක් හරි තුවාලයක්, පාට වෙනසක් — වහාම එන්න, බලන් ඉන්න එපා.

**PATIENT:** හැම දවසෙම, ඔව්.

**DOCTOR:** ඉතින්: gliclazide දැන් දවසට දෙ පාරක්, අලුත් cholesterol tablet එක රෑට, blood සහ urine test, eye referral, මාස තුනකින් ඔක්කොම results එක්ක මම ඔයාව හම්බ වෙන්නම්. ප්‍රශ්න මොනවහරි?

**PATIENT:** නෑ, දොස්තර, ඔක්කොම පැහැදිලියි. ස්තූතියි.

**DOCTOR:** හොඳයි. Mrs. Fernando — ඒ plain tea එක. ඊළඟ සැරේ මම අහනවා!

---

## Romanised reading guide (for the readers)

Turn-by-turn phonetic guide. English terms in English spelling, pronounced as
English. `D:` = doctor, `P:` = patient.

1. **D:** Good morning, Mrs. Fernando. WaaDi wenna. *diabetes check-up* ekata neda aawe?
2. **P:** Ow, dostara. Giya wataawe iNdan maasa thunak wuNaa.
3. **D:** Saamaanyayen kohomada inne?
4. **P:** Narakama næ, dostara. Æth me dawaswala goDak *thirst* ekayi — wathura bonna hithenawaa. Iita amatharawa eka deyak karadarayi — mage kakul. Rǣta, de pæththema, pichchenawaa wage, kooDællo yanawaa wage *tingling* ekak. Samahara welaawata nindhen æharenawaa.
5. **D:** Meka kochchara kaaleka iNdanda?
6. **P:** Maasa dekak witara æthi dæn.
7. **D:** De kakulema ekawageda? Hiri waetenawaa wage — koTTa uDa æwidinawaa wage dænenawada? Kakulwala thuwaalayak, *ulcer* ekak thiyenawada?
8. **P:** De kakulema, ow. Tikak hiri wageth thiyenawaa. Thuwaala næ — mama balanawaa, duwa kiwwaa balanna kiyalaa.
9. **D:** Oyaa balanawaa kiyana eka goDak hoNDayi. Dæn, *sugar control* eka. Oyaa *metformin* eka udeeta ekayi rǣta ekayi — *gram* eka bægin — *gliclazide* 80 udeeta, thaama ehemada ganne?
10. **P:** Ow dostara, mama magaharinne næ. *pressure* ekata *losartan* 50 ekath thiyenawaa.
11. **D:** *sugar* aDu wena *episode* — wewlanawaa, daaDiya daanawaa, klaantha wage — ehema welaa thiyenawada?
12. **P:** Næ, ehema mukuth næ.
13. **D:** Gedaradi *sugar* eka balanawada?
14. **P:** Puthaa *machine* ekak aran dunnaa. Udee, kanna kalin *sugar* eka saamaanyayen 160 witara. Samahara daata 170.
15. **D:** Oyaage anthima *HbA1c* eka — maasa thune *average* eka pennana *test* eka — 8.4. Apita oon 7ta waDaa aDuwen. Ithin *fasting readings* saha *HbA1c* eka dekama kiyanne ekama kathaawa — *control* eka thiyenna oon thæna næ. Kæma gæna kiyanna. Æththa kiyanna dæn!
16. **P:** *(hinaa wenawaa)* Dostara, mama *normal* widihata kanawaa. Dawalta *bath*, rǣta paan nætnam *string hoppers*.
17. **D:** Kochchara *bath* da? Athin pennanna.
18. **P:** ...HoNDa *plate* ekak, dostara. *tea* ekata *sugar* — hændi dekak, dawasata de paarak. Dannawaa, dannawaa.
19. **D:** *(hinaa wenawaa)* Mama kiyanna kalin oyaa kiwwaa. *exercise* ekak — æwidinawada?
20. **P:** Ehema næ. Mage daNa, dostara.
21. **D:** *chest pain*, æwidina kota husma waetenawada? Æswala awulak — boNda wenawaa wage?
22. **P:** *chest pain* næ. Æs hoNDayi, æth *eye check* eka karalaa awuruddakata waDaa wenawaa.
23. **D:** Eka api ada hadamu. Dæn mama *examine* karannam. Mulinma *blood pressure* eka... 140 over 85. Giya særeta waDaa hoNDayi, æth *diabetes* ekka mama kæmathiyi tikak aDuwen thiyenawata. Bara... *kilo* 68, kalin wagema. Dæn kakul — sapaththu, mees galawanna. Hama hoNData thiyenawaa, pælum næ, *ulcer* næ. *pulses*... de kakulema dænenawaa, hoNDayi. Dæn æs wahaganna — me hiin *monofilament* eka æNgiliwalata thaTTu karana kota kiyanna... methana?... methana?... methanada?
24. **P:** ...Walalukara eka dænunaa. ÆNgiliwala eewa nam hariyata dænune næ, dostara.
25. **D:** Mama hithuwe ekamayi. Mrs. Fernando, me pichcheema saha aDu wechcha hæNgeema — meka *diabetic nerve damage*, *neuropathy* ekak. Awurudu gaaNak *sugar* eka waediyen thibbama wena deyak. Shareere apita kiyanawaa *control* eka thada karanna kiyalaa, dæn, thawa naraka wenna kalin.
26. **P:** Meka saneepa wenawada, dostara?
27. **D:** Wechcha *damage* eka aapahu hadanna amaaruyi, æth hoNDa *control* eken thawa issarahata yana eka nawathinawaa, pichcheemath boho wita aDu wenawaa. E nisaa ada api wenaskam tikak karamu. Eka — *gliclazide* eka udeeta 80yi rǣta 80yi karanawaa. *metformin* eka ehemama. Deka — *cholesterol tablet* ekak, *atorvastatin*, rǣta ekak, patan gannawaa. *diabetes* ekka api hadawatha kalinma aarakshaa karanawaa; meka *standard*, aluth awulak nisaa neweyi.
28. **P:** Hari, dostara.
29. **D:** Thuna — iiLaNga *visit* ekata kalin *test* tikak: *HbA1c*, *kidney test* eka, *cholesterol*, saha *protein* balanna *urine test* ekak — eeken balanawaa *diabetes* eka *kidney* walata balapaanawada kiyalaa. Hathara — *eye screening* eka. Mama dænma *referral* eka liyanawaa; eyaala æhe pitipasse *photo* gannawaa. Awuruddakata waDaa *diabetes* ekka waediyi.
30. **P:** Mama yanawaa, dostara.
31. **D:** Kæma. *bath* eka dæn ganna pramaaNayen baagayata aDu karanna — ithuru iDa eLawalu, gotukola, mællum, parippu walin purawanna. *tea* eke *sugar* — sampoornayenma nawaththanna. Eka witarak dawasata hathara paarak hændi gaaNak *sugar* kelinma leeta daana ekak. Æwideema — daNa ekka, poDDen patan ganna: hawasata winaadi pahalowak, pætali paare, hari sapaththu daalaa.
32. **P:** *sugar* næthuwama bonnada, dostara? *plain tea* nam goDak sookayi.
33. **D:** *(hinaa wenawaa)* Sati dekakin purudu wenawaa, *promise*. Oyaage kakul: hæma dawasema balanna, duwa kiww wage — uDa, yata, æNgili athara. Mokak hari thuwaalayak, paaTa wenasak — wahaama enna, balan inna epaa.
34. **P:** Hæma dawasema, ow.
35. **D:** Ithin: *gliclazide* dæn dawasata de paarak, aluth *cholesterol tablet* eka rǣta, *blood* saha *urine test*, *eye referral*, maasa thunakin okkoma *results* ekka mama oyaawa hamba wennam. Prashna monawahari?
36. **P:** Næ, dostara, okkoma pæhædiliyi. Sthoothiyi.
37. **D:** HoNDayi. Mrs. Fernando — e *plain tea* eka. IiLaNga sære mama ahanawaa!

---

## For the recordings-eval manifest

Correct the as-spoken text into `recordings/refs/03_diabetes_review_si.txt`
(turn texts concatenated, no speaker labels) before viewing model output. Draft
generated now. Manifest row:

```json
{"id": "03_diabetes_review_si", "audio": "mock_consultations/recordings/03_diabetes_review_si.wav", "reference": "<contents of refs/03_diabetes_review_si.txt>"}
```
