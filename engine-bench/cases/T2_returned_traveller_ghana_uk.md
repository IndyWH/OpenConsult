# T2 — Fever and shivering after a work trip to Ghana (UK private GP) — TRAVEL CASE, DIAGNOSIS NEVER SPOKEN

**Fictional patient:** Mr. Mark Davies, 46, civil engineer
**Setting:** Private GP surgery, central London · **Speakers:** Doctor, Patient
**Target length:** 4–5 minutes
**Purpose:** benchmark case for v1.1 (Task 3i). A febrile returned traveller in
whom the target diagnosis, falciparum malaria, is never named by doctor or
patient. The patient frames it as the office flu or a dodgy takeaway. Travel is
not volunteered; the doctor asks about it only at turn 13, so the updates at
turns 4, 8 and 12 show whether the CDS asks about travel by itself. He is
moderately unwell with no severe features, so the alarm must fire on the
picture (fever after West Africa, lapsed prophylaxis), not on shock or
confusion.

Not part of the repo. Lives in v1.1-logs/travel/ and is read only by the bench.

## Expected clinical content (marking scheme)

- **Target diagnosis:** Plasmodium falciparum malaria, uncomplicated at
  presentation, returned from Ghana 9 days ago, prophylaxis taken
  irregularly and stopped on return.
- **Reasonable in the differential:** typhoid or enteric fever, dengue, viral
  illness or influenza, gastroenteritis, sepsis, viral hepatitis, Lassa fever
  less likely.
- **Key positives:** cyclical fever with rigors and drenching sweats for 3 days,
  39.8 at peak; headache; myalgia, back pain; anorexia; vomited twice today;
  loose stools; slight dry cough; dark urine; 3 weeks in Ghana including a week
  at a rural site; no net at the site, many bites; daily prophylaxis missed and
  stopped on return.
- **Key negatives:** no confusion or drowsiness; no jaundice noticed; no
  breathlessness; no dysuria; no rash.
- **Examination:** T 39.1, HR 112, BP 108/68, RR 20, SpO2 97%; pale, dry; no
  jaundice; no rash; neck supple; chest clear; mild left upper quadrant
  tenderness, spleen not felt.
- **Plan (turns 23 to 28):** same-day hospital assessment now; GP phones the
  medical team; urgent blood film the same day; treatment the same day if
  positive; not to drive; 999 if confused, drowsy or breathless.

## Expected urgent_actions (marking scheme)

- **Should fire:** yes. Fever in a traveller back from sub-Saharan Africa is a
  same-day emergency until a blood film has excluded it, because it can become
  severe within hours.
- **Expected content:** same-day hospital referral for an urgent blood film (and
  rapid antigen test), FBC, U&E, LFT, glucose.
- **Expected first fire:** once travel to Ghana is known (update at turn 16 at
  the latest).
- **Expected clearing:** the doctor arranges same-day hospital assessment at the
  end; the alarm should clear by the final update.

## Pass marks

To be set by the owner before any run.

---

**DOCTOR:** Hello, come in and take a seat. What's brought you in today?

**PATIENT:** Thanks. I've had some sort of bug for three days and it's not shifting. Fever, shivering, the works. Half the office has had flu, so I expect it's that, but my wife made me come.

**DOCTOR:** Let's go through it. When did it start, and what has the temperature been doing?

**PATIENT:** Sunday evening. I felt cold and started shaking, properly shaking, teeth chattering, under two duvets. Then I got boiling hot, and then I was drenched in sweat. It's done that every day since, usually in the afternoon or evening. In between I feel washed out but not too bad.

**DOCTOR:** That sounds horrible. Have you measured your temperature?

**PATIENT:** It was thirty-nine point eight last night, during one of the shaking bouts.

**DOCTOR:** What else? Headache, aches, anything else you've noticed?

**PATIENT:** A headache, yes, a dull one all over. My muscles ache, my back mostly. And I've gone off my food completely.

**DOCTOR:** Any sickness or diarrhoea?

**PATIENT:** I was sick twice this morning, and I've had the runs a couple of times. I had a dodgy takeaway on Saturday, so I wondered about that.

**DOCTOR:** Any cough, breathlessness or chest pain? Any burning when you pass urine?

**PATIENT:** A bit of a dry cough, nothing much. No burning. My wee's quite dark, but I haven't been drinking much.

**DOCTOR:** Have you been abroad in the last few months?

**PATIENT:** Yes, actually. I got back from Ghana nine days ago. I was out there for three weeks for work, on a road project. Mostly in Accra, but we spent a week at a site upcountry.

**DOCTOR:** That's really helpful. Did the travel clinic give you any tablets to take while you were out there?

**PATIENT:** They gave me some daily tablets. I took them most days, but they upset my stomach, so I missed a few. And I stopped them when I got home. I didn't really see the point once I was back.

**DOCTOR:** And mosquito bites? Did you use a net or repellent?

**PATIENT:** I had a net at the hotel in Accra, but not at the site. I got bitten quite a lot on my ankles and arms, mostly in the evenings.

**DOCTOR:** Have you felt confused or drowsy, or has anyone said you're not making sense? Any yellowing of your eyes?

**PATIENT:** No, my head's clear, I'm just tired. My wife hasn't said anything about my eyes.

**DOCTOR:** I'd like to examine you now. ... Your temperature is thirty-nine point one, your pulse is one hundred and twelve, and your blood pressure is one hundred and eight over sixty-eight. You're breathing twenty times a minute and your oxygen is ninety-seven percent. You look pale and a bit dry. There's no yellowing of your eyes and no rash. Your neck is supple and your chest is clear. Your tummy is soft. It's a little tender under the left ribs, but I can't feel your spleen.

**PATIENT:** So is it flu, then?

**DOCTOR:** I don't think we can call this flu. A fever like yours after a trip to West Africa needs a blood test today, looked at under the microscope, and that can't wait until tomorrow.

**PATIENT:** Today? I've got meetings this afternoon.

**DOCTOR:** I'm afraid the meetings will have to wait. Some infections from that part of the world can become serious very quickly, within a day or two, even when you feel only moderately unwell. I'm going to ring the medical team at the hospital now and send you straight there to be seen today. They'll do the blood test and start treatment the same day if it's positive.

**PATIENT:** Okay. You're worrying me a bit now. Can I drive myself?

**DOCTOR:** I'd rather you didn't drive with a temperature like this. Can your wife take you? If she can't, we'll arrange transport. If you become confused, very drowsy or breathless before you get there, call 999.

**PATIENT:** She's in the car park. I'll go straight there. Thank you, doctor.
