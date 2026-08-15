"""The 100-case linguistic benchmark corpus (docs/linguistic-benchmark.md).

Each case is a French prompt + a learner answer with a hand-judged expected
verdict. `golden` cases are unambiguous and must always classify correctly;
non-golden "difficult/ambiguous" cases have a best-guess expected verdict but
are allowed to miss without failing the benchmark (see the module docstring
in test_linguistic_benchmark.py for the acceptance gates).

Coverage tags mirror the checklist in docs/linguistic-benchmark.md, plus two
added this session to stress-test the evaluation-v3 acceptability-vs-
optimality rule: "acceptability-not-optimality" and "regional-variant".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.evaluations.enums import Verdict


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    french_text: str
    preferred_translation: str
    user_answer: str
    expected_verdict: Verdict
    golden: bool = False
    coverage: tuple[str, ...] = ()
    note: str = ""
    alternatives: list[str] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)
    hint_used: bool = False


NATURAL_CASES = [
    BenchmarkCase(
        id="nat-check-verify",
        french_text="Je dois vérifier ça d'abord.",
        preferred_translation="I need to check that first.",
        alternatives=["Let me check that first."],
        user_answer="I need to verify that first.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        golden=True,
        coverage=("acceptability-not-optimality", "american-usage"),
        note="'Verify' is less frequent than 'check' in casual speech but "
        "equally acceptable; frequency alone is never a penalty.",
    ),
    BenchmarkCase(
        id="nat-start-begin",
        french_text="Nous devons commencer la réunion à l'heure.",
        preferred_translation="We need to start the meeting on time.",
        user_answer="We need to begin the meeting on time.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("acceptability-not-optimality",),
        note="'Begin' vs 'start' is a pure register/frequency preference, not "
        "a naturalness defect.",
    ),
    BenchmarkCase(
        id="nat-think-believe",
        french_text="Je pense qu'il a raison.",
        preferred_translation="I think he's right.",
        user_answer="I believe he's right.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        golden=True,
        coverage=("acceptability-not-optimality",),
        note="'Believe' is slightly more formal than 'think' but fully "
        "natural and unambiguous here.",
    ),
    BenchmarkCase(
        id="nat-contraction-future",
        french_text="Je ne pense pas qu'il vienne.",
        preferred_translation="I don't think he's coming.",
        user_answer="I don't think he'll come.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("contractions", "will-would"),
    ),
    BenchmarkCase(
        id="nat-alt-look-into",
        french_text="Je vais me renseigner sur les horaires.",
        preferred_translation="I'm going to find out about the schedule.",
        user_answer="I'll look into the schedule.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("natural-alternative", "phrasal-verbs"),
    ),
    BenchmarkCase(
        id="nat-present-perfect-full-form",
        french_text="J'ai déjà vu ce film.",
        preferred_translation="I've already seen this movie.",
        user_answer="I have already seen this movie.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        golden=True,
        coverage=("present-perfect-vs-simple-past", "contractions"),
        note="Omitting the contraction does not make an answer 'unnecessarily "
        "formal' or unnatural, especially in writing.",
    ),
    BenchmarkCase(
        id="nat-professional-register",
        french_text="Je vous remercie de votre patience.",
        preferred_translation="Thank you for your patience.",
        user_answer="I appreciate your patience.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("professional-register",),
        contexts=["professional email"],
    ),
    BenchmarkCase(
        id="nat-informal-valid",
        french_text="Ça marche pour moi.",
        preferred_translation="That works for me.",
        user_answer="Sounds good to me.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("informal-valid", "natural-alternative"),
    ),
    BenchmarkCase(
        id="nat-modal-could-would",
        french_text="Pourriez-vous m'aider avec ça ?",
        preferred_translation="Could you help me with that?",
        user_answer="Would you be able to help me with that?",
        expected_verdict=Verdict.CORRECT_NATURAL,
        golden=True,
        coverage=("modals",),
    ),
    BenchmarkCase(
        id="nat-conditional-past",
        french_text="Si j'avais su, je serais venu plus tôt.",
        preferred_translation="If I had known, I would have come earlier.",
        user_answer="If I'd known, I would've come earlier.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("conditionals", "contractions"),
    ),
    BenchmarkCase(
        id="nat-preposition-arrived-home",
        french_text="Je suis arrivé à la maison à 8 heures.",
        preferred_translation="I got home at 8.",
        user_answer="I arrived home at 8.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("prepositions", "natural-alternative"),
    ),
    BenchmarkCase(
        id="nat-article-plays-piano",
        french_text="Il joue du piano.",
        preferred_translation="He plays the piano.",
        user_answer="He plays piano.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("articles",),
        note="Both 'plays the piano' and 'plays piano' are standard American "
        "English.",
    ),
    BenchmarkCase(
        id="nat-phrasal-dropped-project",
        french_text="Elle a laissé tomber le projet.",
        preferred_translation="She gave up on the project.",
        user_answer="She dropped the project.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("phrasal-verbs", "natural-alternative"),
    ),
    BenchmarkCase(
        id="nat-question-tag-right",
        french_text="Il fait beau, n'est-ce pas ?",
        preferred_translation="It's nice out, isn't it?",
        user_answer="It's nice out, right?",
        expected_verdict=Verdict.CORRECT_NATURAL,
        golden=True,
        coverage=("question-tags",),
        note="'Right?' is a very common natural substitute for a tag "
        "question in American English.",
    ),
    BenchmarkCase(
        id="nat-negative-interrogative",
        french_text="Tu ne viens pas ce soir ?",
        preferred_translation="Aren't you coming tonight?",
        user_answer="You're not coming tonight?",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("negative-interrogative",),
    ),
    BenchmarkCase(
        id="nat-multi-sentence",
        french_text="J'étais fatigué. Donc je suis rentré tôt.",
        preferred_translation="I was tired. So I went home early.",
        user_answer="I was tired, so I headed home early.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("multi-sentence-context", "phrasal-verbs"),
        contexts=["casual conversation with a friend"],
    ),
    BenchmarkCase(
        id="nat-regional-do-the-shopping",
        french_text="Je vais faire mes courses.",
        preferred_translation="I'm going to go grocery shopping.",
        alternatives=["I'm going to the grocery store."],
        user_answer="I'm going to do the shopping.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        golden=True,
        coverage=("regional-variant",),
        note="British-flavored phrasing, but widely understood in American "
        "English with no ambiguity — must not be downgraded.",
    ),
    BenchmarkCase(
        id="nat-alt-meet-up",
        french_text="On se retrouve à quelle heure ?",
        preferred_translation="What time are we meeting?",
        user_answer="What time should we meet up?",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("natural-alternative", "phrasal-verbs"),
    ),
    BenchmarkCase(
        id="nat-attend-meeting",
        french_text="Je dois assister à la réunion.",
        preferred_translation="I have to attend the meeting.",
        user_answer="I have to go to the meeting.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("natural-alternative",),
        note="Contrasts with inc-assist-meeting, where 'assister' is "
        "mistranslated via the false friend 'assist'.",
    ),
    BenchmarkCase(
        id="nat-will-would-reported",
        french_text="Il a dit qu'il viendrait demain.",
        preferred_translation="He said he would come tomorrow.",
        user_answer="He said he'd come tomorrow.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("will-would", "contractions"),
    ),
    BenchmarkCase(
        id="nat-alt-got-done",
        french_text="J'ai fini mes devoirs hier.",
        preferred_translation="I finished my homework yesterday.",
        user_answer="I got my homework done yesterday.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("natural-alternative", "phrasal-verbs"),
    ),
    BenchmarkCase(
        id="nat-preposition-across-the-street",
        french_text="Elle habite en face de la banque.",
        preferred_translation="She lives across from the bank.",
        user_answer="She lives across the street from the bank.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("prepositions",),
    ),
    BenchmarkCase(
        id="nat-word-order-adverb",
        french_text="Je vais probablement arriver en retard.",
        preferred_translation="I'll probably be late.",
        user_answer="I'll likely be late.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("word-order", "acceptability-not-optimality"),
    ),
    BenchmarkCase(
        id="nat-literal-still-standard",
        french_text="Merci de m'avoir aidé.",
        preferred_translation="Thanks for helping me.",
        user_answer="Thank you for helping me.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("literal-french-translation",),
        note="Not every French-adjacent structure is a calque error — this "
        "one is standard English too, contrasting with the calque cases in "
        "the INCORRECT/ambiguous buckets.",
    ),
    BenchmarkCase(
        id="nat-idiom-paraphrase",
        french_text="Il pleut des cordes.",
        preferred_translation="It's raining really hard.",
        user_answer="It's pouring outside.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("natural-alternative",),
    ),
]

UNNATURAL_CASES = [
    BenchmarkCase(
        id="unnat-investigate-vs-check",
        french_text="Je vais vérifier si Mike vient à la réunion.",
        preferred_translation="I'll check.",
        alternatives=["I'll find out.", "Let me check."],
        user_answer="I'll investigate it.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        golden=True,
        coverage=("connotation-shift",),
        contexts=["casual reply to a colleague asking if Mike is coming to the meeting"],
        note="'Investigate' implies looking into a problem/incident/crime; "
        "wrong connotation for casually checking on a colleague's attendance.",
    ),
    BenchmarkCase(
        id="unnat-diary-vs-planner",
        french_text="Je vais noter mes rendez-vous dans mon agenda.",
        preferred_translation="I'm going to put my appointments in my planner.",
        user_answer="I'm going to put my appointments in my diary.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        golden=True,
        coverage=("regional-variant",),
        note="'Diary' in American English usually means a personal journal, "
        "not a planner — real risk of being misunderstood, unlike the "
        "'do the shopping' natural regional case.",
    ),
    BenchmarkCase(
        id="unnat-convene-casual",
        french_text="On se voit ce soir ?",
        preferred_translation="Are we still on for tonight?",
        user_answer="Shall we convene this evening?",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register",),
        contexts=["casual text between close friends"],
        note="'Convene' is bureaucratic/formal register, jarringly mismatched "
        "for a casual text between friends.",
    ),
    BenchmarkCase(
        id="unnat-lose-my-time",
        french_text="Il m'a fait perdre mon temps.",
        preferred_translation="He wasted my time.",
        user_answer="He made me lose my time.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("literal-french-translation",),
        note="Word-for-word calque of 'faire perdre son temps' — genuinely "
        "awkward, not merely a minor preference.",
    ),
    BenchmarkCase(
        id="unnat-make-shopping",
        french_text="J'ai besoin de faire du shopping.",
        preferred_translation="I need to go shopping.",
        user_answer="I need to make shopping.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("literal-french-translation",),
        note="Meaning stays fully clear, but 'make shopping' is not a "
        "collocation a native would ever produce.",
    ),
    BenchmarkCase(
        id="unnat-cephalalgia",
        french_text="J'ai un peu mal à la tête.",
        preferred_translation="I have a bit of a headache.",
        user_answer="I am experiencing cephalalgia.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        golden=True,
        coverage=("professional-register",),
        contexts=["casual chat with a friend"],
        note="Clinical jargon totally mismatched for casual small talk.",
    ),
    BenchmarkCase(
        id="unnat-equal-to-me",
        french_text="Ça m'est égal.",
        preferred_translation="I don't care either way.",
        alternatives=["It doesn't matter to me."],
        user_answer="It is equal to me.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("literal-french-translation",),
        note="Literal calque of 'égal', genuinely strange to a native ear "
        "though still parseable.",
    ),
    BenchmarkCase(
        id="unnat-might-i-request-salt",
        french_text="Tu peux me passer le sel ?",
        preferred_translation="Can you pass the salt?",
        user_answer="Might I request that you pass the salt?",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("modals", "professional-register"),
        contexts=["casual family dinner"],
    ),
    BenchmarkCase(
        id="unnat-threw-away-studies",
        french_text="Elle a laissé tomber ses études.",
        preferred_translation="She dropped out of school.",
        user_answer="She threw away her studies.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("phrasal-verbs",),
        note="'Threw away' implies discarding an object; an odd collocation "
        "applied to 'studies', though meaning is still roughly inferable.",
    ),
    BenchmarkCase(
        id="unnat-accomplish-a-pause",
        french_text="Je dois faire une pause.",
        preferred_translation="I need to take a break.",
        user_answer="I must accomplish a pause.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("literal-french-translation",),
        contexts=["casual chat with a coworker"],
    ),
    BenchmarkCase(
        id="unnat-retire-for-the-evening",
        french_text="Je vais me coucher.",
        preferred_translation="I'm going to bed.",
        user_answer="I am going to retire for the evening.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        golden=True,
        coverage=("professional-register",),
        contexts=["telling a roommate you're heading to bed"],
        note="Overly formal/archaic register for talking to a roommate.",
    ),
    BenchmarkCase(
        id="unnat-writing-implement",
        french_text="T'as un stylo ?",
        preferred_translation="Got a pen?",
        alternatives=["Do you have a pen?"],
        user_answer="Might you be in possession of a writing implement?",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register", "modals"),
        contexts=["asking a classmate"],
    ),
    BenchmarkCase(
        id="unnat-rigorous-vs-strict",
        french_text="Elle est trop stricte avec ses employés.",
        preferred_translation="She's too strict with her employees.",
        user_answer="She is too rigorous with her employees.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("connotation-shift",),
        note="'Rigorous' typically describes methods/analysis, not a "
        "person's disciplinary manner — a genuine connotation mismatch, "
        "though still understandable in context.",
    ),
    BenchmarkCase(
        id="unnat-domicile-remain",
        french_text="Je vais rester à la maison ce weekend.",
        preferred_translation="I'm going to stay home this weekend.",
        user_answer="I am going to remain at my domicile this weekend.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register", "literal-french-translation"),
        contexts=["casual weekend-plans chat"],
    ),
    BenchmarkCase(
        id="unnat-partake-beverage",
        french_text="On va prendre un verre après le travail ?",
        preferred_translation="Want to grab a drink after work?",
        user_answer="Shall we partake in a beverage following our labor?",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register",),
        contexts=["casual chat between coworkers"],
    ),
    BenchmarkCase(
        id="unnat-impediment-vs-came-up",
        french_text="Il a eu un empêchement de dernière minute.",
        preferred_translation="Something came up for him at the last minute.",
        user_answer="He had an impediment at the last minute.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("connotation-shift",),
        note="'Impediment' usually implies a physical/speech obstruction, "
        "not a scheduling conflict — odd but still parseable.",
    ),
    BenchmarkCase(
        id="unnat-disoriented-novel-application",
        french_text="Je suis un peu perdu avec ce nouveau logiciel.",
        preferred_translation="I'm a bit lost with this new software.",
        user_answer="I am somewhat disoriented in relation to this novel software application.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register",),
        contexts=["casually asking a coworker for help"],
    ),
    BenchmarkCase(
        id="unnat-vehicular-congestion",
        french_text="Désolé pour le retard, y'a eu un bouchon.",
        preferred_translation="Sorry I'm late, there was traffic.",
        user_answer="I apologize for my tardiness; a vehicular congestion occurred.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        golden=True,
        coverage=("professional-register",),
        contexts=["texting a friend"],
        note="Legalistic/bureaucratic phrasing, jarring for a casual text.",
    ),
    BenchmarkCase(
        id="unnat-forthright",
        french_text="Il faut que je sois franc avec toi.",
        preferred_translation="I need to be honest with you.",
        user_answer="It is necessary that I be forthright with you.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register", "modals"),
        contexts=["personal conversation"],
    ),
    BenchmarkCase(
        id="unnat-transmit-communication",
        french_text="Je vais lui envoyer un petit message.",
        preferred_translation="I'm going to send her a quick message.",
        user_answer="I am going to transmit a brief communication to her.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("professional-register",),
        contexts=["casual personal plans"],
    ),
]

WRITING_ISSUE_CASES = [
    BenchmarkCase(
        id="write-dont-hes",
        french_text="Je ne pense pas qu'il vienne.",
        preferred_translation="I don't think he's coming.",
        user_answer="i dont think hes coming",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        golden=True,
        coverage=("writing-only-apostrophe-capitalization", "contractions"),
    ),
    BenchmarkCase(
        id="write-havent-review",
        french_text="Je n'ai pas eu le temps de le relire.",
        preferred_translation="I haven't had time to review it.",
        user_answer="i havent had time to reveiw it",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-thats-nice",
        french_text="C'est vraiment gentil de ta part.",
        preferred_translation="That's really nice of you.",
        user_answer="thats really nice of you",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-shoud-go",
        french_text="Je crois qu'on devrait y aller.",
        preferred_translation="I think we should go.",
        user_answer="i think we shoud go",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-shes-not-arrived",
        french_text="Elle n'est pas encore arrivée.",
        preferred_translation="She hasn't arrived yet.",
        user_answer="shes not arrived yet",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-im-sorry",
        french_text="Je suis désolé pour hier.",
        preferred_translation="I'm sorry about yesterday.",
        user_answer="im sorry about yesterday",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization", "contractions"),
    ),
    BenchmarkCase(
        id="write-where-meet",
        french_text="On se retrouve où ?",
        preferred_translation="Where should we meet?",
        user_answer="where should we meet",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        golden=True,
        coverage=("writing-only-punctuation",),
        note="Punctuation/capitalization only — spoken aloud this is "
        "identical to a natural production.",
    ),
    BenchmarkCase(
        id="write-thats-good-idea",
        french_text="Je pense que c'est une bonne idée.",
        preferred_translation="I think that's a good idea.",
        user_answer="i think thats a good idea",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-hasnt-anwsered",
        french_text="Il n'a pas encore répondu.",
        preferred_translation="He hasn't answered yet.",
        user_answer="he hasnt anwsered yet",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-dont-know-if-can-come",
        french_text="Je ne sais pas si je peux venir.",
        preferred_translation="I don't know if I can come.",
        user_answer="i dont know if i can come",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization", "contractions"),
    ),
    BenchmarkCase(
        id="write-realy-fun",
        french_text="C'était vraiment amusant.",
        preferred_translation="That was really fun.",
        user_answer="that was realy fun",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        golden=True,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-shed-be-here-soon",
        french_text="Elle m'a dit qu'elle arriverait bientôt.",
        preferred_translation="She told me she'd be here soon.",
        user_answer="she told me shed be here soon",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization", "contractions", "will-would"),
    ),
    BenchmarkCase(
        id="write-cant-decide",
        french_text="Je n'arrive pas à me décider.",
        preferred_translation="I can't decide.",
        user_answer="i cant decide",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-apostrophe-capitalization",),
    ),
    BenchmarkCase(
        id="write-were-we're-homophone",
        french_text="Nous sommes prêts pour l'examen.",
        preferred_translation="We're ready for the exam.",
        user_answer="were ready for the exam",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        golden=True,
        coverage=("writing-only-apostrophe-capitalization",),
        note="'were' without the apostrophe collides with the real word "
        "'were' (past tense), but spoken aloud 'were ready' and 'we're "
        "ready' are homophones — still a writing-only issue by the rule "
        "(would sound identical if spoken as intended).",
    ),
    BenchmarkCase(
        id="write-can-you-help-please",
        french_text="Tu peux m'aider s'il te plaît ?",
        preferred_translation="Can you help me please?",
        user_answer="can you help me please",
        expected_verdict=Verdict.CORRECT_WITH_WRITING_ISSUES,
        coverage=("writing-only-punctuation",),
    ),
]

INCORRECT_CASES = [
    BenchmarkCase(
        id="inc-assist-meeting",
        french_text="Je vais assister à la réunion.",
        preferred_translation="I'm going to attend the meeting.",
        user_answer="I'm going to assist the meeting.",
        expected_verdict=Verdict.INCORRECT,
        golden=True,
        coverage=("false-friends",),
        note="'assister à' (to attend) mistranslated via the false friend "
        "'assist' — changes meaning from attending to helping.",
    ),
    BenchmarkCase(
        id="inc-actually-currently",
        french_text="Je vais actuellement travailler sur ce projet.",
        preferred_translation="I'm currently working on this project.",
        user_answer="I'm actually working on this project.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'actuellement' (currently) mistranslated as 'actually' — "
        "changes meaning (right now vs. contrary to expectation).",
    ),
    BenchmarkCase(
        id="inc-demanded-asked",
        french_text="Il a demandé un renseignement.",
        preferred_translation="He asked for information.",
        user_answer="He demanded information.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'demander' (to ask) mistranslated as 'demand' — a request "
        "becomes a demand.",
    ),
    BenchmarkCase(
        id="inc-present-for-past",
        french_text="Hier, je suis allé au marché.",
        preferred_translation="Yesterday, I went to the market.",
        user_answer="Yesterday, I go to the market.",
        expected_verdict=Verdict.INCORRECT,
        golden=True,
        coverage=("tense-changes-meaning",),
        note="Present tense for a dated, completed past event is a "
        "meaningful grammar error a native wouldn't make.",
    ),
    BenchmarkCase(
        id="inc-present-for-bounded-past",
        french_text="Je vivais à Paris pendant cinq ans.",
        preferred_translation="I lived in Paris for five years.",
        user_answer="I live in Paris for five years.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("tense-changes-meaning", "present-perfect-vs-simple-past"),
        note="Present tense obscures whether she still lives there or the "
        "period is finished.",
    ),
    BenchmarkCase(
        id="inc-conditional-type-shift",
        french_text="Si j'étais riche, j'achèterais une maison.",
        preferred_translation="If I were rich, I would buy a house.",
        user_answer="If I am rich, I will buy a house.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("conditionals",),
        note="Switches a hypothetical/counterfactual conditional to a real, "
        "plausible future one — materially changes the meaning.",
    ),
    BenchmarkCase(
        id="inc-until-vs-by",
        french_text="Je dois retourner mes formulaires avant vendredi.",
        preferred_translation="I need to turn in my forms by Friday.",
        user_answer="I need to turn in my forms until Friday.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("prepositions", "meaning-materially-changed"),
        note="'Until Friday' implies an ongoing action, wrongly changing a "
        "one-time deadline into a recurring one.",
    ),
    BenchmarkCase(
        id="inc-spared-saved",
        french_text="Elle a économisé beaucoup d'argent.",
        preferred_translation="She saved a lot of money.",
        user_answer="She spared a lot of money.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'économiser' (to save up) mistranslated as 'spare' — wrong "
        "meaning entirely.",
    ),
    BenchmarkCase(
        id="inc-eventually-possibly",
        french_text="Je vais éventuellement changer de travail.",
        preferred_translation="I might possibly change jobs.",
        user_answer="I will eventually change jobs.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'éventuellement' (possibly) mistranslated as 'eventually' — "
        "an uncertain possibility becomes a certain future event.",
    ),
    BenchmarkCase(
        id="inc-cork-traffic-jam",
        french_text="Le bouchon a duré deux heures.",
        preferred_translation="The traffic jam lasted two hours.",
        user_answer="The cork lasted two hours.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'bouchon' (traffic jam, in context) mistranslated literally "
        "as 'cork' — completely wrong meaning.",
    ),
    BenchmarkCase(
        id="inc-agency-agenda",
        french_text="Il travaille dans une agence immobilière.",
        preferred_translation="He works at a real estate agency.",
        user_answer="He works at a real estate agenda.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'agenda' (a schedule/planner) instead of 'agency' — the "
        "sentence no longer describes a coherent workplace.",
    ),
    BenchmarkCase(
        id="inc-polished-polite",
        french_text="Je vais rester poli avec lui.",
        preferred_translation="I'm going to stay polite with him.",
        user_answer="I'm going to stay polished with him.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'poli' (polite) vs. 'polished' (shiny/refined) — a plausible "
        "spelling-confusion learner error that changes the meaning.",
    ),
    BenchmarkCase(
        id="inc-word-order-reversal",
        french_text="Le chien a mordu le facteur.",
        preferred_translation="The dog bit the mail carrier.",
        user_answer="The mail carrier bit the dog.",
        expected_verdict=Verdict.INCORRECT,
        golden=True,
        coverage=("word-order",),
        note="Reversed subject/object completely inverts who did what to "
        "whom — an unambiguous meaning reversal.",
    ),
    BenchmarkCase(
        id="inc-forgot-bringing",
        french_text="Elle a oublié d'apporter son parapluie.",
        preferred_translation="She forgot to bring her umbrella.",
        user_answer="She forgot bringing her umbrella.",
        expected_verdict=Verdict.INCORRECT,
        golden=True,
        coverage=("meaning-materially-changed",),
        note="'Forget to do' (failed to do it) vs. 'forget doing' (doesn't "
        "recall having done it) carry genuinely different meanings — this "
        "flips whether she brought the umbrella at all.",
    ),
    BenchmarkCase(
        id="inc-borrowed-lent",
        french_text="Elle m'a prêté sa voiture la semaine dernière.",
        preferred_translation="She lent me her car last week.",
        user_answer="She borrowed me her car last week.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'Borrow' (receive) vs. 'lend' (give) reversal — a well-known "
        "ESL meaning-reversal error.",
    ),
    BenchmarkCase(
        id="inc-still-doesnt-work-here",
        french_text="Il ne travaille plus ici.",
        preferred_translation="He doesn't work here anymore.",
        user_answer="He still doesn't work here.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("negative-interrogative", "meaning-materially-changed"),
        note="'ne...plus' (not anymore) mistranslated as 'still...not' — "
        "reverses the temporal implication (used to but stopped, vs. never "
        "did).",
    ),
    BenchmarkCase(
        id="inc-caught-missed-train",
        french_text="Nous avons raté le train de justesse.",
        preferred_translation="We just barely missed the train.",
        user_answer="We just barely caught the train.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends", "meaning-materially-changed"),
        note="'rater' (to miss) mistranslated with its opposite 'caught' — "
        "a direct outcome reversal.",
    ),
    BenchmarkCase(
        id="inc-weekdays-weekends",
        french_text="Le magasin ferme à 18h en semaine.",
        preferred_translation="The store closes at 6pm on weekdays.",
        user_answer="The store closes at 6pm on weekends.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("meaning-materially-changed",),
        note="'en semaine' (on weekdays) mistranslated as 'weekends' — "
        "reverses which days are meant.",
    ),
    BenchmarkCase(
        id="inc-failed-managed",
        french_text="Elle a réussi à convaincre son patron.",
        preferred_translation="She managed to convince her boss.",
        user_answer="She failed to convince her boss.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("meaning-materially-changed",),
        note="'réussir à' (to succeed in) mistranslated with its opposite "
        "'failed to' — a direct success/failure reversal.",
    ),
    BenchmarkCase(
        id="inc-will-two-years-ago",
        french_text="Ils se sont mariés il y a deux ans.",
        preferred_translation="They got married two years ago.",
        user_answer="They will get married two years ago.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("tense-changes-meaning", "will-would"),
        note="Mixing future 'will' with a clearly past time marker produces "
        "an incoherent, meaning-obscuring tense clash.",
    ),
    BenchmarkCase(
        id="inc-causes-relieves-pain",
        french_text="Ce médicament soulage la douleur.",
        preferred_translation="This medication relieves the pain.",
        user_answer="This medication causes the pain.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends", "meaning-materially-changed"),
        note="'soulager' (to relieve) mistranslated as its near-opposite "
        "'causes' — reverses the medication's effect.",
    ),
    BenchmarkCase(
        id="inc-currently-fluently",
        french_text="Elle parle couramment trois langues.",
        preferred_translation="She speaks three languages fluently.",
        user_answer="She speaks three languages currently.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'couramment' (fluently) confused with the near-homophone "
        "'currently' — changes a skill-level claim into a temporal one.",
    ),
    BenchmarkCase(
        id="inc-remind-call-back",
        french_text="Je te rappelle dans cinq minutes.",
        preferred_translation="I'll call you back in five minutes.",
        user_answer="I remind you in five minutes.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("false-friends",),
        note="'rappeler' (to call back) mistranslated as 'remind' — an "
        "entirely different action.",
    ),
    BenchmarkCase(
        id="inc-delayed-canceled",
        french_text="Le vol a été annulé à cause du mauvais temps.",
        preferred_translation="The flight was canceled because of bad weather.",
        user_answer="The flight was delayed because of bad weather.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("meaning-materially-changed",),
        note="'Canceled' and 'delayed' are materially different outcomes "
        "for the listener.",
    ),
    BenchmarkCase(
        id="inc-dropped-negation",
        french_text="Ne t'inquiète pas, tout va bien se passer.",
        preferred_translation="Don't worry, everything's going to be fine.",
        user_answer="Worry, everything's going to be fine.",
        expected_verdict=Verdict.INCORRECT,
        golden=True,
        coverage=("negative-interrogative",),
        note="Dropping the negation entirely reverses reassurance into its "
        "opposite instruction.",
    ),
]

AMBIGUOUS_CASES = [
    BenchmarkCase(
        id="amb-depends-of",
        french_text="Cela dépend de la situation.",
        preferred_translation="It depends on the situation.",
        user_answer="It depends of the situation.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("prepositions",),
        note="A common non-native preposition slip; understandable and "
        "meaning-preserving. Reasonable graders might call this NATURAL "
        "(very minor) instead — not INCORRECT since meaning is 100% clear.",
    ),
    BenchmarkCase(
        id="amb-tac-au-tac",
        french_text="Elle a répondu du tac au tac.",
        preferred_translation="She shot back a quick reply.",
        user_answer="She responded tac for tac.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("literal-french-translation",),
        note="Idiom-calque severity is contested: could be judged INCORRECT "
        "(genuinely unclear without knowing the idiom) instead of UNNATURAL.",
    ),
    BenchmarkCase(
        id="amb-marie-only",
        french_text="Marie seule a compris la blague.",
        preferred_translation="Only Marie understood the joke.",
        user_answer="Marie only understood the joke.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("word-order",),
        note="This exact misplaced-modifier construction is extremely "
        "common in native casual speech with the intended meaning; a strict "
        "grammarian might instead call it ambiguous/unnatural.",
    ),
    BenchmarkCase(
        id="amb-double-negative",
        french_text="Je n'ai vu personne.",
        preferred_translation="I didn't see anyone.",
        user_answer="I didn't see nobody.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("negative-interrogative",),
        note="Recognizable dialectal double negative with the same intended "
        "meaning; contested between UNNATURAL (non-standard) and INCORRECT "
        "(a formal reversal) given the app's standard-American-English "
        "target.",
    ),
    BenchmarkCase(
        id="amb-police-novel",
        french_text="Je suis en train de lire un roman policier.",
        preferred_translation="I'm reading a detective novel.",
        user_answer="I'm reading a police novel.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("false-friends",),
        note="Non-standard genre term but a reader can roughly infer a "
        "crime-related novel; contested between UNNATURAL and INCORRECT "
        "depending on how much weight is given to genre precision.",
    ),
    BenchmarkCase(
        id="amb-will-vs-going-to-confident",
        french_text="Je suis confiant que ça va marcher.",
        preferred_translation="I'm confident this will work.",
        user_answer="I'm confident this is going to work.",
        expected_verdict=Verdict.CORRECT_NATURAL,
        coverage=("will-would", "acceptability-not-optimality"),
        note="Stress-tests whether the model over-applies a 'will vs. "
        "going to' nuance that isn't actually meaningful in this context.",
    ),
    BenchmarkCase(
        id="amb-in-purpose",
        french_text="Il a fait exprès de me bousculer.",
        preferred_translation="He bumped into me on purpose.",
        user_answer="He bumped into me in purpose.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("prepositions",),
        note="Minor preposition slip, understandable; contested vs. NATURAL "
        "given how common and minor the slip is.",
    ),
    BenchmarkCase(
        id="amb-much-grown",
        french_text="Elle a beaucoup grandi depuis l'année dernière.",
        preferred_translation="She's grown a lot since last year.",
        user_answer="She has much grown since last year.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("word-order",),
        note="Awkward, non-native adverb placement; understandable. "
        "Contested vs. INCORRECT if the word order is judged to impede "
        "quick comprehension.",
    ),
    BenchmarkCase(
        id="amb-it-says-rain",
        french_text="On dirait qu'il va pleuvoir.",
        preferred_translation="It looks like it's going to rain.",
        user_answer="It says that it will rain.",
        expected_verdict=Verdict.CORRECT_UNNATURAL,
        coverage=("literal-french-translation",),
        note="Literal calque of 'on dirait' as 'it says'; the rain "
        "prediction still comes through from context. Contested vs. "
        "INCORRECT since 'it says' could confuse who/what is speaking.",
    ),
    BenchmarkCase(
        id="amb-revalue-make-it-up",
        french_text="Je te revaudrai ça.",
        preferred_translation="I'll make it up to you.",
        alternatives=["I owe you one."],
        user_answer="I will revalue that to you.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("literal-french-translation",),
        note="'Revalue' is a real English word with a specific, wrong "
        "financial connotation — actively misleading, not merely stiff. "
        "Contested vs. UNNATURAL since it is a very literal calque.",
    ),
    BenchmarkCase(
        id="amb-legs-to-neck",
        french_text="Il a pris ses jambes à son cou.",
        preferred_translation="He ran off as fast as he could.",
        user_answer="He took his legs to his neck.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("literal-french-translation",),
        note="Literal idiom translation, essentially incomprehensible as "
        "intended English to a typical American listener; contested vs. "
        "UNNATURAL for a generous reader steeped in French idiom.",
    ),
    BenchmarkCase(
        id="amb-smells-fir-tree",
        french_text="Ça sent le sapin.",
        preferred_translation="Things aren't looking good.",
        user_answer="It smells like fir tree.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("literal-french-translation",),
        note="Literal idiom translation; meaning is lost to a listener with "
        "no knowledge of the French idiom.",
    ),
    BenchmarkCase(
        id="amb-has-some-dog",
        french_text="Elle a du chien.",
        preferred_translation="She's got a certain charm.",
        user_answer="She has some dog.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("literal-french-translation",),
        note="Literal idiom mistranslation; meaning is lost and could even "
        "read as insulting.",
    ),
    BenchmarkCase(
        id="amb-hold-you-at-the-current",
        french_text="Je vais me renseigner et je te tiens au courant.",
        preferred_translation="I'll look into it and keep you posted.",
        user_answer="I will inform myself and hold you at the current.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("literal-french-translation",),
        note="Garbled literal calque of 'tenir au courant'; contested vs. "
        "UNNATURAL since a generous reader might partially recover the "
        "meaning.",
    ),
    BenchmarkCase(
        id="amb-dont-come-back-from-it",
        french_text="Je n'en reviens pas.",
        preferred_translation="I can't believe it.",
        user_answer="I don't come back from it.",
        expected_verdict=Verdict.INCORRECT,
        coverage=("literal-french-translation",),
        note="Literal calque of 'revenir' applied to an idiom meaning "
        "disbelief; genuinely confusing to a listener unfamiliar with the "
        "source idiom.",
    ),
]

BENCHMARK_CASES = (
    NATURAL_CASES + UNNATURAL_CASES + WRITING_ISSUE_CASES + INCORRECT_CASES + AMBIGUOUS_CASES
)
