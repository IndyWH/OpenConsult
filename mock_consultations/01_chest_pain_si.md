# 01 — Chest pain on exertion (Sinhala / English code-switched)

**Fictional patient:** Mr. Ranjith Perera, 52, three-wheeler driver
**Speakers:** Doctor, Patient · **Target length:** 4–5 minutes read aloud
**Language:** Sri Lankan spoken Sinhala with embedded English medical/loan terms
("pressure eka", drug names, test names) — the way a real SL surgery sounds. The
patient speaks mostly Sinhala; the doctor mixes both.

## Which evaluation this serves

- **Primary — Phase 5 Sinhala ASR recordings evaluation** (pre-registered in
  `evals/2026-07-10_sinhala_asr_benchmark.md`, § Pre-registration). This is a
  **code-switching** test case: the per-script-class error metric and the
  mechanical English-term recall both key off the embedded Latin-script terms
  below. The as-spoken Sinhala turns are the source for the recordings-eval
  reference (`recordings/refs/01_chest_pain_si.txt` — draft generated now, to be
  corrected to what was actually said before any model output is viewed).
- **Secondary** — once Sinhala ASR + the translation layer land, this exercises
  the CDS / notes pipeline in Sinhala against the same **Expected clinical
  content** marking scheme as the English `01_chest_pain_en.md` (clinical content
  is identical; only the language differs).

## Expected clinical content (marking scheme for AI outputs)

Identical to `01_chest_pain_en.md` — the clinical facts are the same:

- **Differential:** stable angina / possible ACS (leading), GORD, musculoskeletal pain
- **Key positives:** exertional central chest tightness ×2 weeks, radiation to left arm once, smoker 20/day, father had heart attack at 60, untreated high blood pressure
- **Key negatives:** no pain at rest, no breathlessness at rest, no chest wall tenderness
- **Examination:** BP 150/95, pulse 88 regular, heart sounds normal, lungs clear
- **Plan:** ECG today, urgent referral for cardiology work-up (troponin, exercise testing), start aspirin after ECG, strong smoking-cessation advice, safety-netting — go straight to hospital if pain at rest >15 min

## English-term list (for the code-switching metric)

The pre-registered metric (benchmark record § "Code-switching: per-script-class
error attribution" and § Pre-registration step 5) scores how well the ASR keeps
the **English medical vocabulary** that the downstream pipeline needs. Freeze this
list before viewing any hypothesis.

**Clinically load-bearing English terms present in the as-spoken reference**
(these are the ones a miss actually costs the pipeline):

`chest`, `pain`, `pressure` / `blood pressure`, `ECG`, `aspirin`, `angina`,
`cardiology`, `pulse`, `murmur`, `heart attack`, `cigarette` (smoking history),
`hospital`, `emergency`.

**Other English / loan tokens present (context, not clinically load-bearing):**
`three-wheeler`, `packet`, `weekend`, `arrack`, `beer`, `TV`, `shed`, `rest`,
`medical camp`, `diabetes`, `cholesterol`, `stroke`, `allergy`, `pattern`,
`tightness`, `normal`, `clear`, `test`, `tablet`, `dose`, `refer` / `referral`,
`urgent`, `clinic`, `Mr`, `Perera`.

**Scoring notes (from the pre-registration):**
- *Strict script matching.* If the model writes a Sinhala transliteration of an
  English term (e.g. `ECG` → `ඊසීජී`, `aspirin` → `ඇස්පිරින්`) it counts as a
  **miss** in the mechanical metric, because CDS prompts, note citations and RAG
  retrieval operate on the English string. The manual adjudication pass
  (step 6) records transliterated hits separately.
- English-term recall is order-insensitive: a term counts as recalled if it
  survives anywhere in the utterance as a Latin token ≥ 3 chars.
- Numbers (`88`, `150`, `95`, `52`, `20`, `15`) are kept as digits and scored in
  the digit class, not the Latin class.

---

## Consultation — as spoken (reference transcript)

Sinhala/English code-switched. Speaker labels stay in Latin caps so
`app/mock_scripts.py` parses these turns unchanged; the concatenated turn texts
(no labels) are the ASR reference.

**DOCTOR:** Good morning, එන්න, වාඩි වෙන්න. අද මොකද වුණේ?

**PATIENT:** Good morning, දොස්තර මහත්තයෝ. මට chest එකේ, මැද්දෙ, pain එකක් එනවා. දැන් සති දෙකක් විතර වෙනවා.

**DOCTOR:** එහෙමද. මේ pain එක කොහොමද දැනෙන්නෙ? විස්තර කරන්න.

**PATIENT:** හිර වෙනවා වගේ, දොස්තර. බර දෙයක් chest එකට තද කරනවා වගේ.

**DOCTOR:** මේක එන්නෙ කවදද, කොයි වෙලාවෙද?

**PATIENT:** වැඩක් කරන කොට තමයි වැඩිය. ඊයෙ three-wheeler එක shed එකට තල්ලු කරන කොට ගොඩක් ආවා. ගෙදර පඩි නගින කොටත් එනවා.

**DOCTOR:** කොච්චර වෙලාවක් තියෙනවද?

**PATIENT:** විනාඩි පහක් දහයක් විතර. නැවතිලා rest එකක් ගත්තම යනවා.

**DOCTOR:** මේ pain එක වෙන තැනකට යනවද — අතට, කරට, පිටට?

**PATIENT:** එක පාරක් වම් අතට ගියා. ඒක නම් මට ටිකක් බය හිතුනා, ඇත්තටම. ඒකයි ආවෙ.

**DOCTOR:** හොඳට ආවෙ. නිකන් ඉන්න කොට — TV එක බලන් වාඩි වෙලා ඉන්න කොට — එනවද?

**PATIENT:** නෑ නෑ. වැඩක් කරන කොට විතරයි.

**DOCTOR:** එක්කම හුස්ම ගන්න අමාරුද? දාඩිය දානවද, ඔක්කාරයක් තියෙනවද?

**PATIENT:** pain එක එන කොට ටිකක් හුස්ම වැටෙනවා. වමනෙ නම් නෑ, එහෙම දෙයක් නෑ.

**DOCTOR:** ඇසිඩ් එනවා වගේ, පිච්චෙනවා වගේ දැනෙනවද? කෑම කෑවම, නිදාගන්න වෙලාවෙ වැඩි වෙනවද?

**PATIENT:** ලොකු rice packet එකක් කෑවම සමහර වෙලාවට පිච්චෙනවා, ඒත් මේ තද වෙන pain එක වෙනස්. මේක අලුත්.

**DOCTOR:** chest එකේ තද කරලා බැලුවම, ඇඟ පෙරළුවම රිදෙනවද?

**PATIENT:** නෑ දොස්තර, මම තද කරලා බැලුවා. මුකුත් නෑ.

**DOCTOR:** දැන් ඔයාගෙ සාමාන්‍ය සෞඛ්‍යය ගැන ප්‍රශ්න ටිකක්. ඔයා cigarette බොනවද?

**PATIENT:** ඔව්... දවසකට packet එකක් විතර. විස්සක්. අවුරුදු තිහක් විතර, දොස්තර.

**DOCTOR:** arrack, beer — බොනවද?

**PATIENT:** weekend එකට විතරයි. ග්ලාස් දෙක තුනක්.

**DOCTOR:** දන්න කිසි ලෙඩක් තියෙනවද — diabetes, pressure, cholesterol?

**PATIENT:** පෝය අවුරුද්දෙ medical camp එකකදි කිව්වා pressure එක වැඩියි කියලා. දොස්තර කෙනෙක්ව හම්බ වෙන්න කිව්වා, ඒත් මම ගියේ නෑ. සාමාන්‍යයෙන් හොඳට ඉන්නවනෙ, ඒ නිසා.

**DOCTOR:** පවුලේ? heart attack, stroke වගේ?

**PATIENT:** මගේ තාත්තට heart attack එකක් ආවා. එයාට අවුරුදු හැටක් විතර ඇති එතකොට.

**DOCTOR:** නිතිපතා ගන්න මොකක් හරි බෙහෙතක් තියෙනවද? allergy මොකක් හරි?

**PATIENT:** මුකුත් නෑ දොස්තර. allergy මම දන්න විදිහට නෑ.

**DOCTOR:** හරි. දැන් මම ඔයාව examine කරන්නම්. මුලින්ම pulse එක බලන්නම්... pulse එක 88, regular. දැන් blood pressure එක... ඒක 150 over 95 — camp එකේ කිව්ව වගේ, ඇත්තටම වැඩියි. හදවත listen කරන්නම්... heart sounds normal, murmur නෑ. ලොකුවට හුස්මක් ගන්න... ආයෙත්... lungs clear. chest එකේ මෙතන තද කරන කොට — රිදෙනවද?

**PATIENT:** රිද්දීමක් නෑ, දොස්තර.

**DOCTOR:** හොඳයි. දැන්, Mr. Perera, මම හිතන දේ කියන්නම්. මේ pattern එක — වැඩක් කරන කොට එන, rest එකෙන් සන්සුන් වෙන, වම් අතට යන tightness එකක්, cigarette බොන, pressure වැඩි, තාත්තට heart එකේ ප්‍රශ්නයක් තිබුණ කෙනෙක්ට — මට බය හිතෙනවා මේක angina වෙන්න පුළුවන් කියලා. ඒ කියන්නෙ හදවතට ලේ යවන blood vessels ටික පට්ට වෙලා ඇති.

**PATIENT:** මේක heart attack එකක්ද, දොස්තර?

**DOCTOR:** මම හිතන්නෙ නෑ ඔයාට දැන් heart attack එකක් වෙනවා කියලා, ඒත් මේක අපි බරපතලව ගන්න ඕන warning sign එකක්. Plan එක මෙහෙමයි. අපි දැන්ම, මේ කාමරේදිම, ECG එකක් — heart එකේ tracing එකක් — ගන්නවා. ඊට පස්සෙ මම ඔයාව cardiology clinic එකට urgent විදිහට refer කරනවා, blood test සහ තව heart test වලට. ECG එක ගත්තට පස්සෙ, පොඩි dose එකේ aspirin එකකුත් පටන් ගන්නවා, දවසකට එකක්.

**PATIENT:** හරි, දොස්තර.

**DOCTOR:** තව දෙයක් දෙකක්, ඒවා බෙහෙත් තරමටම වැදගත්. cigarette එක නවත්තන්නම ඕන — සම්පූර්ණයෙන්ම. හරියටම මේ විදිහටයි ඒක හදවතට හානි කරන්නෙ. pressure එකත් හදන්න ඕන; ඊළඟ visit එකේදි confirm කරලා tablet එකක් පටන් ගන්න වෙයි.

**PATIENT:** මම අඩු කරන්න try කරනවා...

**DOCTOR:** අඩු කරනවා මදි, දැන් වෙන දේ එක්ක. නවත්තන්න උදව් කරන clinic තියෙනවා — විස්තර දෙන්නම්. දැන්, ගොඩක් වැදගත්: නිකන් ඉන්න කොට මේ pain එක ආවොත්, විනාඩි පහළොවකට වඩා තියෙනවා නම්, සන්සුන් වෙන්නෙ නැත්නම් — බලන් ඉන්න එපා, මෙහෙ එන්නත් එපා — කෙලින්ම hospital එකට, emergency එකට යන්න. තේරුණාද?

**PATIENT:** කෙලින්ම hospital එකට. තේරුණා, දොස්තර.

**DOCTOR:** හොඳයි. දැන් ඒ ECG එක ගමු, referral letter එකත් එක්ක පස්සෙ මම ඔයාව හම්බ වෙන්නම්.

**PATIENT:** ස්තූතියි, දොස්තර.

---

## Romanised reading guide (for the readers)

A practical phonetic guide, aligned turn-by-turn with the transcript above. Long
vowels are doubled (`aa`, `ee`, `oo`); English terms are left in English spelling
and should be **pronounced as English** — that code-switch is the whole point.
`D:` = doctor, `P:` = patient. Read at natural conversational pace.

1. **D:** Good morning, enna, waadi wenna. Ada mokada wuNe?
2. **P:** Good morning, dostara mahaththayo. Mata *chest* eke, maedde, *pain* ekak enawaa. Dæn sati dekak witara wenawaa.
3. **D:** Ehemada. Me *pain* eka kohomada dænenne? Wisthara karanna.
4. **P:** Hira wenawaa wage, dostara. Bara deyak *chest* ekata thada karanawaa wage.
5. **D:** Meka enne kawadada, koyi welaawheda?
6. **P:** Waedak karana kota thamayi waediya. Iiye *three-wheeler* eka *shed* ekata thallu karana kota goDak aawaa. Gedara paDi nagina kotath enawaa.
7. **D:** Kochchara welaawak thiyenawada?
8. **P:** Winaadi pahak dahayak witara. Naewathilaa *rest* ekak gaththama yanawaa.
9. **D:** Me *pain* eka wena thaenakata yanawada — atata, karata, pitata?
10. **P:** Eka paarak wam atata giyaa. Eka nam mata tikak baya hithunaa, æththatama. Ekayi aawe.
11. **D:** HoNData aawe. Nikan inna kota — *TV* eka balan waaDi welaa inna kota — enawada?
12. **P:** Næ næ. Waedak karana kota witarayi.
13. **D:** Ekkama husma ganna amaaruda? DaaDiya daanawada, okkaarayak thiyenawada?
14. **P:** *pain* eka ena kota tikak husma waetenawaa. Wamane nam næ, ehema deyak næ.
15. **D:** Acid enawaa wage, pichchenawaa wage dænenawada? Kæma kæwama, nidaaganna welaawe waedi wenawada?
16. **P:** Loku *rice packet* ekak kæwama samahara welaawata pichchenawaa, æth me thada wena *pain* eka wenas. Meka aluth.
17. **D:** *chest* eke thada karalaa bæluwama, æNga peraLuwama ridenawada?
18. **P:** Næ dostara, mama thada karalaa bæluwaa. Mukuth næ.
19. **D:** Dæn oyaage saamaanya saukhyaya gæna prashna tikak. Oyaa *cigarette* bonawada?
20. **P:** Ow... dawasakata *packet* ekak witara. Wissak. Awurudu thihak witara, dostara.
21. **D:** *arrack*, *beer* — bonawada?
22. **P:** *weekend* ekata witarayi. Glass deka thunak.
23. **D:** Danna kisi ledak thiyenawada — *diabetes*, *pressure*, *cholesterol*?
24. **P:** Poya awurudde *medical camp* ekakadi kiwwaa *pressure* eka waediyi kiyalaa. Dostara kenekwa hamba wenna kiwwaa, æth mama giye næ. Saamaanyayen hoNData innawane, e nisaa.
25. **D:** Pawule? *heart attack*, *stroke* wage?
26. **P:** Mage thaaththata *heart attack* ekak aawaa. Eyaata awurudu haetak witara æthi ethakota.
27. **D:** Nithipathaa ganna mokak hari beheth thiyenawada? *allergy* mokak hari?
28. **P:** Mukuth næ dostara. *allergy* mama danna widihata næ.
29. **D:** Hari. Dæn mama oyaawa *examine* karannam. Mulinma *pulse* eka balannam... *pulse* eka 88, *regular*. Dæn *blood pressure* eka... eka 150 over 95 — *camp* eke kiwwa wage, æththatama waediyi. Hadawatha *listen* karannam... *heart sounds normal*, *murmur* næ. Lokuwata husmak ganna... aayeth... *lungs clear*. *chest* eke methana thada karana kota — ridenawada?
30. **P:** Riddeemak næ, dostara.
31. **D:** HoNDayi. Dæn, Mr. Perera, mama hithana de kiyannam. Me *pattern* eka — waedak karana kota ena, *rest* eken sansun wena, wam atata yana *tightness* ekak, *cigarette* bona, *pressure* waedi, thaaththata *heart* eke prashnayak thibuNa kenekta — mata baya hithenawaa meka *angina* wenna puluwan kiyalaa. E kiyanne hadawathata le yawana *blood vessels* tika paTTa welaa æthi.
32. **P:** Meka *heart attack* ekakda, dostara?
33. **D:** Mama hithanne næ oyaata dæn *heart attack* ekak wenawaa kiyalaa, æth meka api barapathalawa ganna oon *warning sign* ekak. *Plan* eka mehemayi. Api dænma, me kaamaredima, *ECG* ekak — *heart* eke *tracing* ekak — gannawaa. Iita passe mama oyaawa *cardiology clinic* ekata *urgent* widihata *refer* karanawaa, *blood test* saha thawa *heart test* walata. *ECG* eka gaththata passe, poDi *dose* eke *aspirin* ekakuth patan gannawaa, dawasakata ekak.
34. **P:** Hari, dostara.
35. **D:** Thawa deyak dekak, ewaa beheth tharamatama waedagath. *cigarette* eka nawaththannama oon — sampoornayenma. Hariyatama me widihatayi eka hadawathata haani karanne. *pressure* ekath hadanna oon; iiLaNga *visit* ekedi *confirm* karalaa *tablet* ekak patan ganna weyi.
36. **P:** Mama aDu karanna *try* karanawaa...
37. **D:** ADu karanawaa madi, dæn wena de ekka. Nawaththanna udaw karana *clinic* thiyenawaa — wisthara dennam. Dæn, goDak waedagath: nikan inna kota me *pain* eka aawoth, winaadi pahalowakata waDaa thiyenawaa nam, sansun wenne nætnam — balan inna epaa, mehe ennath epaa — kelinma *hospital* ekata, *emergency* ekata yanna. Therunaada?
38. **P:** Kelinma *hospital* ekata. Therunaa, dostara.
39. **D:** HoNDayi. Dæn e *ECG* eka gamu, *referral letter* ekath ekka passe mama oyaawa hamba wennam.
40. **P:** Sthoothiyi, dostara.

---

## For the recordings-eval manifest

After recording, correct the as-spoken text (both scripts', Sinhala with English
terms as actually uttered) into `recordings/refs/01_chest_pain_si.txt` — turn
texts concatenated in order, **no** speaker labels (live-path convention;
`as_live_transcript` in `app/mock_scripts.py`). A draft of that file is generated
from this script now; freeze the corrected version before viewing model output,
per the pre-registration. Manifest row:

```json
{"id": "01_chest_pain_si", "audio": "mock_consultations/recordings/01_chest_pain_si.wav", "reference": "<contents of refs/01_chest_pain_si.txt>"}
```
