/*
 * Eat Well, Spend Less — Grocery Budget Check-In
 * Questions, scoring and personalised result generation.
 * Pure logic, no DOM, so it can be tested in Node.
 *
 * SCORING (transparent):
 *  - Each answer in Q1–Q6 carries 0–3 "room to improve" points in one or more
 *    of four areas: spend (spending control), shop (shopping habits),
 *    plan (meal planning), waste (food waste).
 *  - Each area is converted to a percentage of its maximum.
 *  - The four areas count equally: score = average of the four, rounded (0–100).
 *  - Higher score = more room to improve. Helpful habits score 0.
 *  - Q7 and Q8 are not scored; they only personalise the wording.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.EWSLQuizData = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var AREAS = [
    { key: "spend", label: "Spending control" },
    { key: "shop", label: "Grocery shopping habits" },
    { key: "plan", label: "Meal planning" },
    { key: "waste", label: "Food waste" }
  ];

  var LEVELS = [
    {
      n: 1, min: 0, max: 24, name: "You're Building Good Habits",
      text: "Your answers suggest that you already have some useful habits in place. Small adjustments to shopping lists, seasonal ingredients, and leftovers may help you save even more.",
      headline: "You're already doing a lot right."
    },
    {
      n: 2, min: 25, max: 49, name: "A Few Habits Could Make a Difference",
      text: "You have a foundation to build on, but unplanned purchases or inconsistent meal planning may be making your grocery budget harder to manage.",
      headline: "A few small habits could make a real difference."
    },
    {
      n: 3, min: 50, max: 74, name: "Your Budget Needs a Little Structure",
      text: "Your answers suggest that grocery planning, ingredient reuse, and spending limits could make a meaningful difference to your routine.",
      headline: "A little structure could take a lot of pressure off."
    },
    {
      n: 4, min: 75, max: 100, name: "Time for a Fresh Start",
      text: "Your answers suggest that grocery spending may feel difficult to control right now. Start small with a realistic shopping list, simple meals, and a plan to use what you already have.",
      headline: "A fresh start can be small — and it can begin today."
    }
  ];

  /* ------------------------------------------------------------------ */
  /* Questions. pts = points per area, tags = challenge themes (weights) */
  /* ------------------------------------------------------------------ */
  var QUESTIONS = [
    {
      id: "q1", area: "Your grocery budget", short: "End of the week",
      title: "How does your grocery spending usually feel by the end of the week?",
      intro: "Let's start gently. There are no wrong answers here.",
      after: "Thank you for being honest — that helps.",
      options: [
        { label: "I'm usually within my budget.", icon: "check", pts: {}, tags: {},
          strength: "You usually finish the week within your grocery budget." },
        { label: "I sometimes spend more than I planned.", icon: "wallet", pts: { spend: 1 }, tags: { drift: 1 } },
        { label: "My money runs out before the week does.", icon: "clock", pts: { spend: 3 }, tags: { runs_out: 3 } },
        { label: "I honestly don't know where it all goes.", icon: "question", pts: { spend: 2 }, tags: { blind: 2 } }
      ]
    },
    {
      id: "q2", area: "Your biggest challenge", short: "Biggest challenge",
      title: "What makes eating well on a budget hardest for you?",
      intro: "Next, let's talk about what gets in the way.",
      after: "That's really common. You're not alone in this.",
      options: [
        { label: "Healthy ingredients seem too expensive.", icon: "tag", pts: { shop: 1 }, tags: { pricey: 1 } },
        { label: "I buy food but still end up ordering takeout.", icon: "bag", pts: { plan: 2 }, tags: { takeout: 2 } },
        { label: "I waste food because I don't use everything in time.", icon: "trash", pts: { waste: 2 }, tags: { waste: 2 } },
        { label: "I shop without a clear plan.", icon: "cart", pts: { shop: 2, plan: 1 }, tags: { no_plan: 2 } },
        { label: "All of the above, honestly.", icon: "sparkle", pts: { shop: 2, plan: 2, waste: 2 },
          tags: { pricey: 1, takeout: 2, waste: 2, no_plan: 2 } }
      ]
    },
    {
      id: "q3", area: "Your shopping habits", short: "At the shop",
      title: "When you go grocery shopping, what usually happens?",
      intro: "Now the shop itself — how does it usually go?",
      after: "Good to know. Plenty of people shop this way.",
      options: [
        { label: "I follow a list and stick to it.", icon: "list", pts: {}, tags: {},
          strength: "You shop with a list and stick to it." },
        { label: "I have a list, but I often buy extra things.", icon: "cart", pts: { shop: 1 }, tags: { extras: 1 } },
        { label: "I buy what looks good at the moment.", icon: "eye", pts: { shop: 3 }, tags: { impulse: 3 } },
        { label: "I shop several times because I forget what I need.", icon: "repeat", pts: { shop: 2 }, tags: { trips: 2 } }
      ]
    },
    {
      id: "q4", area: "Food waste", short: "Food waste",
      title: "How often do you throw away food you bought but never used?",
      intro: "Let's look at what happens to the food afterward.",
      after: "No judgment here — food waste happens to everyone.",
      options: [
        { label: "Rarely. I use almost everything.", icon: "leaf", pts: {}, tags: {},
          strength: "You use almost everything you buy." },
        { label: "Sometimes, especially fresh produce.", icon: "apple", pts: { waste: 1 }, tags: { waste: 1 } },
        { label: "Often, because I buy more than I need.", icon: "trash", pts: { waste: 3 }, tags: { waste: 3 } },
        { label: "I'm not sure how much I actually waste.", icon: "question", pts: { waste: 2 }, tags: { waste_unknown: 2 } }
      ]
    },
    {
      id: "q5", area: "Meal planning", short: "Meal planning",
      title: "What does a typical week of meals look like for you?",
      intro: "Halfway there! Let's peek at your week of meals.",
      after: "Halfway there. You're doing great.",
      options: [
        { label: "I plan most of my meals ahead.", icon: "calendar", pts: {}, tags: {},
          strength: "You plan most of your meals ahead." },
        { label: "I repeat a few meals to save money.", icon: "repeat", pts: { plan: 1 }, tags: {},
          strength: "You repeat a few meals to save money — a strategy that really works." },
        { label: "I decide what to eat day by day.", icon: "sun", pts: { plan: 2 }, tags: { daybyday: 2 } },
        { label: "I often spend extra because I have no plan.", icon: "question", pts: { plan: 3 }, tags: { no_plan: 3 } }
      ]
    },
    {
      id: "q6", area: "Your spending pattern", short: "Going over budget",
      title: "Compared with what you intended to spend, how much do you usually go over your grocery budget?",
      intro: "Just a gentle one about the budget itself.",
      after: "Thanks — nearly done.",
      options: [
        { label: "I rarely go over budget.", icon: "check", pts: {}, tags: {},
          strength: "You rarely go over your grocery budget." },
        { label: "A little extra most weeks.", icon: "wallet", pts: { spend: 1 }, tags: { drift: 1 } },
        { label: "Quite a bit, and it adds up.", icon: "trend", pts: { spend: 3 }, tags: { drift: 3 } },
        { label: "I don't have a clear grocery budget yet.", icon: "pencil", pts: { spend: 2 }, tags: { no_budget: 2 } }
      ]
    },
    {
      id: "q7", area: "Your personal goal", short: "Biggest change",
      title: "If you could change one thing about your food budget, what would make the biggest difference?",
      intro: "Now the fun part: what would you change?",
      after: "That's a goal worth working toward.",
      options: [
        { label: "Spending less on groceries.", icon: "trend", pts: {}, tags: {}, goal: "spend",
          phrase: "spending less on groceries", boost: ["drift", "runs_out", "no_budget"], item: "shopping" },
        { label: "Eating healthier without paying more.", icon: "apple", pts: {}, tags: {}, goal: "healthy",
          phrase: "eating healthier without paying more", boost: ["pricey"], item: "seasonal" },
        { label: "Wasting less food.", icon: "leaf", pts: {}, tags: {}, goal: "waste",
          phrase: "wasting less food", boost: ["waste", "waste_unknown"], item: "waste" },
        { label: "Having meals planned for the whole week.", icon: "calendar", pts: {}, tags: {}, goal: "plan",
          phrase: "having meals planned for the whole week", boost: ["no_plan", "daybyday", "takeout"], item: "plans" },
        { label: "Saving money without feeling deprived.", icon: "heart", pts: {}, tags: {}, goal: "easy",
          phrase: "saving money without feeling deprived", boost: ["pricey", "drift"], item: "recipes" }
      ]
    },
    {
      id: "q8", area: "Your next step", short: "What it would give you",
      title: "Imagine your groceries were planned, your meals were ready, and less food went to waste. What would that give you?",
      intro: "Last one. Take a moment to imagine it.",
      after: "Lovely. That's all my questions!",
      options: [
        { label: "More money for other priorities.", icon: "coin", pts: {}, tags: {}, phrase: "more money for other priorities" },
        { label: "Less stress and more peace of mind.", icon: "smile", pts: {}, tags: {}, phrase: "less stress and more peace of mind" },
        { label: "More time and fewer last-minute meals.", icon: "clock", pts: {}, tags: {}, phrase: "more time and fewer last-minute meals" },
        { label: "All three. That's exactly what I need.", icon: "sparkle", pts: {}, tags: {}, phrase: "more money, more peace of mind and more time" }
      ]
    }
  ];

  /* ------------------------------------------------------------------ */
  /* Challenge themes                                                    */
  /* ------------------------------------------------------------------ */
  var TAGS = {
    drift: { theme: "spend", title: "Spending that drifts past the plan",
      phrase: "spending that drifts a little past your plan",
      detail: "Going over by a bit each week is very common. It usually means the plan needs more room for real life — not that you're doing anything wrong.",
      actions: ["list_limit", "track_week"] },
    runs_out: { theme: "spend", title: "Money running out before the week does",
      phrase: "your grocery money running out before the week does",
      detail: "That is stressful, and it often comes down to how the week's spending is spread out rather than how much you care or try.",
      actions: ["split_shop", "list_limit"] },
    blind: { theme: "spend", title: "Not being sure where the money goes",
      phrase: "not being sure where the money goes",
      detail: "Most of us never see our grocery spending clearly. A week of simple tracking usually makes it far easier to spot what matters.",
      actions: ["track_week", "pantry"] },
    no_budget: { theme: "spend", title: "No clear grocery budget yet",
      phrase: "not having a clear grocery budget yet",
      detail: "A budget doesn't have to be strict. A realistic weekly number gives every shop something to aim at.",
      actions: ["list_limit", "track_week"] },
    extras: { theme: "shop", title: "Extra items that sneak into the basket",
      phrase: "extra items sneaking into the basket",
      detail: "Having a list is already a strong start. Leaving a little room for treats can help it hold up in the shop.",
      good: "Leaving room for one small treat can help the list you already follow hold up in the shop.",
      actions: ["one_extra", "running_list"] },
    impulse: { theme: "shop", title: "Buying what looks good in the moment",
      phrase: "buying what looks good in the moment",
      detail: "Shops are designed to make everything look appealing. A short, specific list gives you something to come back to.",
      actions: ["one_extra", "list_limit"] },
    trips: { theme: "shop", title: "Extra trips to the shop",
      phrase: "extra trips to the shop",
      detail: "Forgetting an item or two is normal, but each extra trip tends to add extra purchases too.",
      actions: ["running_list", "three_meals"] },
    pricey: { theme: "shop", title: "Healthy food feeling out of reach",
      phrase: "healthy ingredients feeling out of reach",
      detail: "Eating well doesn't have to mean expensive ingredients. Seasonal produce, dried staples and store brands go a long way.",
      good: "Seasonal produce, dried staples like beans and lentils, and store brands can make healthy eating much kinder to the budget.",
      actions: ["seasonal_swap", "one_ingredient"] },
    takeout: { theme: "plan", title: "Takeout when the plan falls apart",
      phrase: "takeout filling the gaps when the plan falls apart",
      detail: "Takeout is often a sign of a tired evening, not a lack of willpower. A simple backup meal can make the difference.",
      good: "A simple weekly plan and one or two quick backup meals can turn takeout into a choice rather than a rescue.",
      actions: ["takeout_backup", "three_meals"] },
    no_plan: { theme: "plan", title: "Shopping and cooking without a plan",
      phrase: "shopping and cooking without much of a plan",
      detail: "You don't need a perfect meal plan. Three planned dinners can already change how the week feels.",
      actions: ["three_meals", "one_ingredient"] },
    daybyday: { theme: "plan", title: "Deciding what to eat day by day",
      phrase: "last-minute meal decisions",
      detail: "Deciding every evening is tiring, and it's when takeout and extra shop trips creep in. A few go-to meals take the pressure off.",
      actions: ["three_meals", "takeout_backup"] },
    waste: { theme: "waste", title: "Food bought but not used in time",
      phrase: "food going unused before it can be eaten",
      detail: "Almost everyone throws away some food. Small habits — like using what's near its date first — can change this quickly.",
      actions: ["use_first", "freeze_early", "leftovers"] },
    waste_unknown: { theme: "waste", title: "Not being sure how much goes to waste",
      phrase: "not being sure how much food goes to waste",
      detail: "A quick look at what's in the fridge and cupboards before each shop is often the easiest way to see the real picture.",
      actions: ["use_first", "pantry", "track_week"] },
    /* Only used when someone's answers show very little to improve. */
    p_seasonal: { theme: "shop", title: "Making seasonal ingredients do more",
      phrase: "making seasonal ingredients do more",
      detail: "Seasonal produce is often cheaper and tastier, and it's an easy place to save a little more.",
      good: "Choosing seasonal produce and dried staples is one of the easiest places to stretch your budget a little further.",
      actions: ["seasonal_swap"] },
    p_leftovers: { theme: "waste", title: "Giving leftovers a second life",
      phrase: "giving leftovers a second life",
      detail: "Planning leftovers into the week — rather than hoping they get eaten — is a small habit with a lasting payoff.",
      good: "Planning leftovers into the week, instead of hoping they get eaten, is a small habit that keeps paying off.",
      actions: ["leftovers", "freeze_early"] },
    p_batch: { theme: "plan", title: "Batch cooking for easier weeks",
      phrase: "batch cooking for easier weeks",
      detail: "Cooking a base once (rice, lentils, roasted vegetables) can make the rest of the week mostly assembly.",
      good: "Cooking one base batch and building meals from it can make busy weeks feel much easier.",
      actions: ["one_ingredient", "three_meals"] }
  };

  var ACTIONS = {
    pantry: { title: "Check your pantry first",
      text: "Before your next shop, spend five minutes looking through the fridge, freezer and cupboards. Write down what you already have so you don't buy it twice." },
    three_meals: { title: "Plan three meals around what you already have",
      text: "Pick three dinners that use ingredients already at home, then buy only what's missing. Three is plenty to start." },
    list_limit: { title: "Write a list and set a realistic limit",
      text: "Choose a weekly amount that feels realistic rather than aspirational, and write your list to fit it. Adjust next week; this is practice." },
    one_ingredient: { title: "Choose one versatile ingredient for several meals",
      text: "Beans, lentils, rice, oats or cabbage can anchor breakfast, lunch and dinner. Buying one in a larger pack often costs less per serving." },
    leftovers: { title: "Set aside leftovers for another meal",
      text: "When you cook, portion one serving for tomorrow's lunch or the freezer straight away, before it disappears." },
    track_week: { title: "Track your groceries for one week",
      text: "Keep receipts or jot each purchase in a note on your phone. There's no judging here: you're simply gathering information." },
    split_shop: { title: "Split the week into two smaller shops",
      text: "Dividing your weekly amount across two shops (or two envelopes) can help the money last through to the end of the week." },
    running_list: { title: "Keep a running list on your phone",
      text: "Add items the moment you run out, and take the list with you. It's the simplest way to cut down on extra trips." },
    one_extra: { title: "Try a one-extra rule",
      text: "Allow yourself one unplanned item per trip. You still get a treat, and the list stays in charge." },
    takeout_backup: { title: "Keep a 15-minute backup meal ready",
      text: "Stock the ingredients for something quick, like egg fried rice or beans and rice, so takeout isn't your only fast option on a tiring night." },
    use_first: { title: "Start a \"use first\" list",
      text: "Stick a note on the fridge listing anything close to its best-by date, and cook from that list first." },
    freeze_early: { title: "Freeze it before it spoils",
      text: "Bread, cooked rice, chopped vegetables and leftover portions all freeze well. Pop them in the freezer while they're still fresh." },
    seasonal_swap: { title: "Pick one seasonal fruit or vegetable and one dried staple",
      text: "Choose something in season plus beans, lentils or oats for this week's shop. It's a small swap that is often kind to the budget." }
  };

  var DEFAULT_ACTIONS = ["pantry", "list_limit", "track_week", "leftovers"];

  var THEMES = {
    spend: {
      good: "A realistic weekly limit and one week of simple tracking can show you where your money goes, without any spreadsheet.",
      steps: [
        { when: "Today · 10 minutes", text: "Write down one number you'd be comfortable spending on groceries this week. Aim for realistic, not perfect." },
        { when: "This week", text: "Keep every receipt, or a quick note on your phone, for seven days. You're collecting information, not grading yourself." },
        { when: "At your next shop", text: "Take only your list. If it helps, use cash or a dedicated debit card so your limit is easy to see." }
      ],
      book: "Smart grocery shopping and spending control"
    },
    shop: {
      good: "A short, specific list and a rule for the occasional treat can keep the basket on track without making shopping feel like a chore.",
      steps: [
        { when: "Today · 10 minutes", text: "Check the fridge and cupboards, then write a list with exact quantities (\"6 carrots\", not \"veg\")." },
        { when: "This week", text: "Plan three dinners and make sure everything on your list belongs to one of them." },
        { when: "At your next shop", text: "Stick to the list, and allow yourself one unplanned item so it feels doable rather than strict." }
      ],
      book: "Smart grocery shopping and spending control"
    },
    plan: {
      good: "A simple weekly plan, flexible recipes and a few go-to meals can take the last-minute decisions off your plate.",
      steps: [
        { when: "Today · 10 minutes", text: "Choose three dinners that share ingredients, such as rice, beans and one vegetable." },
        { when: "This week", text: "Cook a base batch once (rice, lentils or roasted vegetables) so weeknight meals become assembly." },
        { when: "At your next shop", text: "Buy only what those three meals and one backup meal need." }
      ],
      book: "Practical meal planning and recipes"
    },
    waste: {
      good: "Using what you already have, like leftovers, the freezer and a \"use first\" list, can stretch every grocery trip further.",
      steps: [
        { when: "Today · 10 minutes", text: "Make a \"use first\" list of anything close to its date and stick it on the fridge." },
        { when: "This week", text: "Cook from that list first, and freeze anything you won't get to in time." },
        { when: "At your next shop", text: "Check your pantry before you leave and buy for slightly fewer meals. Leftovers count as meals." }
      ],
      book: "Batch cooking, ingredient swaps and food-waste reduction"
    }
  };

  /* What is in the e-book, ordered per visitor by relevance. */
  var BOOK_ITEMS = {
    recipes: { title: "50+ budget-friendly recipes",
      text: "Built around beans, grains and vegetables, with plenty of simple dishes that use 5–10 ingredients." },
    plans: { title: "Practical weekly meal plans and shopping lists",
      text: "Four weekly plans (one person, families, vegetarian and quick-prep), each with a shopping list to go with it." },
    shopping: { title: "Smart grocery shopping and spending-control strategies",
      text: "Lists, store layout, store brands, sales, unit-price maths and ways to rein in impulse buys." },
    waste: { title: "Batch cooking, ingredient swaps and food-waste reduction",
      text: "Cook once and eat several times, use what's left, and swap ingredients instead of making another trip." },
    seasonal: { title: "Seasonal meal planning and simple nutrition guidance",
      text: "Seasonal produce guides and low-GI, fibre-and-protein basics for steady energy, without pricey \"health\" foods." },
    bonus: { title: "Bonus resources for budget cooking and smarter shopping",
      text: "20 extra recipes made from the same shopping list, plus a swap table and tracking guides." }
  };
  var BOOK_DEFAULT_ORDER = ["recipes", "plans", "shopping", "waste", "seasonal", "bonus"];
  var THEME_ITEMS = {
    spend: ["shopping", "plans", "bonus"],
    shop: ["shopping", "plans", "seasonal"],
    plan: ["plans", "recipes", "bonus"],
    waste: ["waste", "plans", "recipes"]
  };
  var WHY = {
    spend: "Spending control came up strongly in your answers, so the shopping-and-spending chapter and the weekly shopping lists are a natural place to start.",
    shop: "Your shopping habits stood out, so the grocery-shopping strategies and ready-made shopping lists could help most.",
    plan: "Meal planning stood out in your answers, so the weekly plans and flexible recipes are where this book could help most.",
    waste: "Food waste stood out in your answers, so the batch-cooking, leftover and ingredient-swap strategies are the best place to begin."
  };

  /* ------------------------------------------------------------------ */
  /* Logic                                                               */
  /* ------------------------------------------------------------------ */
  function areaMaxima() {
    var max = {};
    AREAS.forEach(function (a) { max[a.key] = 0; });
    QUESTIONS.forEach(function (q) {
      AREAS.forEach(function (a) {
        var best = 0;
        q.options.forEach(function (o) { best = Math.max(best, o.pts[a.key] || 0); });
        max[a.key] += best;
      });
    });
    return max;
  }

  /** Returns true only if answers is an array of valid option indexes (one per question). */
  function validateAnswers(answers) {
    if (!Array.isArray(answers) || answers.length !== QUESTIONS.length) return false;
    return QUESTIONS.every(function (q, i) {
      var a = answers[i];
      return typeof a === "number" && isFinite(a) && Math.floor(a) === a && a >= 0 && a < q.options.length;
    });
  }

  function levelFor(score) {
    for (var i = 0; i < LEVELS.length; i++) {
      if (score >= LEVELS[i].min && score <= LEVELS[i].max) return LEVELS[i];
    }
    return null;
  }

  function scoreAnswers(answers) {
    if (!validateAnswers(answers)) throw new Error("Invalid answers");
    var maxima = areaMaxima();
    var pts = {};
    AREAS.forEach(function (a) { pts[a.key] = 0; });
    QUESTIONS.forEach(function (q, i) {
      var o = q.options[answers[i]];
      AREAS.forEach(function (a) { pts[a.key] += o.pts[a.key] || 0; });
    });
    var areas = {};
    var sum = 0;
    AREAS.forEach(function (a) {
      var pct = maxima[a.key] ? (pts[a.key] / maxima[a.key]) * 100 : 0;
      areas[a.key] = { label: a.label, pts: pts[a.key], max: maxima[a.key], pct: pct };
      sum += pct;
    });
    var score = Math.round(sum / AREAS.length);
    return { areas: areas, score: score, level: levelFor(score) };
  }

  function joinList(items) {
    if (items.length <= 1) return items.join("");
    if (items.length === 2) return items[0] + " and " + items[1];
    return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
  }

  function capitalise(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function buildResult(answers) {
    var scored = scoreAnswers(answers);
    var chosen = QUESTIONS.map(function (q, i) { return q.options[answers[i]]; });

    /* --- tag weights (only tags the visitor actually reported) --- */
    var weights = {}, firstSeen = {};
    chosen.forEach(function (o, qi) {
      Object.keys(o.tags || {}).forEach(function (t) {
        weights[t] = (weights[t] || 0) + o.tags[t];
        if (firstSeen[t] === undefined) firstSeen[t] = qi;
      });
    });
    var goal = chosen[6], gain = chosen[7];
    (goal.boost || []).forEach(function (t) { if (weights[t]) weights[t] += 1; });

    var ranked = Object.keys(weights).sort(function (a, b) {
      return weights[b] - weights[a] || firstSeen[a] - firstSeen[b];
    });
    var picked = ranked.filter(function (t) { return weights[t] >= 2; }).slice(0, 3);
    if (picked.length < 2) {
      ranked.forEach(function (t) { if (picked.length < 2 && picked.indexOf(t) < 0) picked.push(t); });
    }
    var polished = false;
    ["p_seasonal", "p_leftovers", "p_batch"].forEach(function (t) {
      if (picked.length < 2) { picked.push(t); polished = true; }
    });
    var challenges = picked.map(function (t) {
      return { key: t, title: TAGS[t].title, detail: TAGS[t].detail, theme: TAGS[t].theme };
    });

    /* --- strengths (answers showing helpful habits) --- */
    var strengths = [];
    chosen.forEach(function (o) { if (o.strength) strengths.push(o.strength); });
    strengths = strengths.slice(0, 3);
    if (!strengths.length) {
      strengths.push("You took a few minutes to look honestly at your grocery habits. That's a real first step, and not an easy one.");
    }

    /* --- three practical actions: round-robin over the ranked challenges --- */
    var actionKeys = [];
    for (var round = 0; round < 3 && actionKeys.length < 3; round++) {
      picked.forEach(function (t) {
        var k = TAGS[t].actions[round];
        if (k && actionKeys.length < 3 && actionKeys.indexOf(k) < 0) actionKeys.push(k);
      });
    }
    DEFAULT_ACTIONS.forEach(function (k) {
      if (actionKeys.length < 3 && actionKeys.indexOf(k) < 0) actionKeys.push(k);
    });
    var actions = actionKeys.map(function (k) { return { key: k, title: ACTIONS[k].title, text: ACTIONS[k].text }; });

    /* --- primary / secondary theme: driven by the challenges actually shown,
           with the four area percentages only used to break ties --- */
    var order = ["waste", "plan", "spend", "shop"]; // final tie-break order
    var themeWeight = { waste: 0, plan: 0, spend: 0, shop: 0 };
    picked.forEach(function (t) { themeWeight[TAGS[t].theme] += (weights[t] || 0.1); });
    var themes = order.slice().sort(function (a, b) {
      return themeWeight[b] - themeWeight[a] ||
        scored.areas[b].pct - scored.areas[a].pct ||
        order.indexOf(a) - order.indexOf(b);
    });
    var primary = themes[0], secondary = themes[1];

    /* --- personalised paragraph --- */
    var level = scored.level;
    var phrases = challenges.map(function (c) { return TAGS[c.key].phrase; });
    // Polish suggestions ("p_*") only belong in the sentence for people with strong habits;
    // for everyone else, "<polish tip> may be making it harder" would read as nonsense.
    var realPhrases = challenges.filter(function (c) { return c.key.indexOf("p_") !== 0; })
      .map(function (c) { return TAGS[c.key].phrase; });
    if (level.n > 1 && realPhrases.length) phrases = realPhrases;
    // Use the most relevant tag's own tailored sentence if it has one, otherwise the theme's.
    var lead = null;
    picked.forEach(function (t) { if (!lead && TAGS[t].theme === primary) lead = TAGS[t]; });
    var goodNews = (lead && lead.good) || THEMES[primary].good;
    var personal;
    if (level.n === 1) {
      personal = "Looking a little closer, the places with room to improve are " + joinList(phrases) + ". " +
        goodNews + " You don't need expensive ingredients or complicated recipes to polish things further.";
    } else {
      personal = "Looking a little closer, " + joinList(phrases) + " may be making it harder to stay within your grocery budget. " +
        "The good news? " + goodNews +
        " You don't need expensive ingredients or complicated recipes to get started.";
    }

    var supportive = level.n === 1
      ? "Good habits are worth protecting, and a little polish goes a long way."
      : "Your grocery habits can change, one small decision at a time.";
    var echo = "You said the biggest difference would be " + goal.phrase +
      ", and that having your groceries and meals sorted would give you " + gain.phrase + ". That's a very reasonable thing to want, and it's what the steps here are aimed at.";

    /* --- e-book contents in order of relevance --- */
    var bookOrder = [];
    function pushItem(k) { if (bookOrder.indexOf(k) < 0) bookOrder.push(k); }
    THEME_ITEMS[primary].slice(0, 2).forEach(pushItem);
    pushItem(THEME_ITEMS[secondary][0]);
    pushItem(goal.item);
    BOOK_DEFAULT_ORDER.forEach(pushItem);
    var book = bookOrder.map(function (k, i) {
      return {
        key: k, title: BOOK_ITEMS[k].title, text: BOOK_ITEMS[k].text,
        startHere: i < 2, forGoal: k === goal.item
      };
    });

    return {
      score: scored.score,
      level: level,
      areas: scored.areas,
      challenges: challenges,
      polished: polished,
      strengths: strengths,
      actions: actions,
      headline: level.headline,
      supportive: supportive,
      personal: personal,
      echo: echo,
      primary: primary,
      secondary: secondary,
      why: WHY[primary],
      plan: THEMES[primary].steps,
      planBook: THEMES[primary].book,
      book: book
    };
  }


  /* ------------------------------------------------------------------ */
  /* Entry-popup message: shown instead of the full results page when    */
  /* the quiz is the required step before the home page. Written from    */
  /* what the book actually contains; makes no promises about outcomes.  */
  /* ------------------------------------------------------------------ */
  var GATE = {
    waste: {
      topic: "Wasting less of what you buy",
      heroKicker: "Built for wasting less of what you buy",
      headline: "Let's stop good food, and good money, from going in the bin.",
      body: "Eat Well, Spend Less is built around using everything you buy: weekly plans that reuse the same few ingredients, leftovers planned as tomorrow's lunch, and simple freezing tricks for anything that won't be eaten in time.",
      solves: [
        { title: "Plans that reuse ingredients", text: "Each weekly meal plan repeats a handful of staples in different forms, so what you buy actually gets used." },
        { title: "Batch cooking and planned leftovers", text: "A Sunday prep routine turns one round of cooking into several meals, with leftovers built in." },
        { title: "Freeze it before it spoils", text: "Easy preservation and freezing methods for produce and cooked food, so less ends up in the bin." }
      ],
      cta: "Show me how to waste less", target: "#inside", targetName: "What's inside"
    },
    plan: {
      topic: "Planning your week without the scramble",
      heroKicker: "Built for weeks without the last-minute scramble",
      headline: "Imagine opening the fridge and already knowing what's for dinner.",
      body: "That's what this book is built for: weekly meal plans with the shopping list done for you, and flexible recipes that take the daily \u201cwhat are we eating?\u201d decision off your plate.",
      solves: [
        { title: "Four weekly meal plans", text: "One for a single person, one for families, one vegetarian and one quick-prep, each with its own shopping list." },
        { title: "50+ simple recipes", text: "Most use just 5\u201310 ingredients, built on beans, grains and vegetables you can swap around." },
        { title: "Quick dinners and Sunday prep", text: "20-minute dinners and a short weekly prep routine, so busy evenings don't default to takeout." }
      ],
      cta: "Show me how to plan my week", target: "#recipes", targetName: "Sample recipes"
    },
    spend: {
      topic: "Making your grocery money last",
      heroKicker: "Built for making your grocery money last",
      headline: "Let's make your grocery money last the whole week.",
      body: "The book starts with a realistic weekly target ($45\u2013$50 for one to two people) and shows you how to meet it: a core shopping list, pantry staples, store brands, unit-price maths and simple ways to keep impulse buys in check.",
      solves: [
        { title: "A weekly budget framework", text: "A core shopping list and cost boundaries, so you know what a week of groceries should look like before you go." },
        { title: "Smarter shopping", text: "Store brands, bulk-buying, sales and unit-price comparisons, explained simply." },
        { title: "Spending control and tracking", text: "Easy ways to track what you spend and see where it goes, without a spreadsheet." }
      ],
      cta: "Show me how to make it last", target: "#budget", targetName: "The budget"
    },
    shop: {
      topic: "Shopping trips that match the plan",
      heroKicker: "Built for shopping trips that match the plan",
      headline: "A short list, a calm shop, and a basket that matches the plan.",
      body: "The shopping chapter is all about staying in control in the store: a specific list built from your meals, tips on how supermarkets are laid out, store brands, and an easy way to compare unit prices.",
      solves: [
        { title: "Lists built from your meals", text: "Every weekly plan comes with a shopping list, so you buy for meals you'll actually cook." },
        { title: "Store layout and impulse control", text: "Where the fresh, affordable staples sit, and how to keep extras from sneaking in." },
        { title: "Unit-price maths", text: "A simple way to tell which pack really costs less, even when the shelf price suggests otherwise." }
      ],
      cta: "Show me how to shop smarter", target: "#inside", targetName: "What's inside"
    }
  };

  /** Builds the popup's closing message from a finished result. */
  function gateMessage(result) {
    var theme = result.primary;
    var g = GATE[theme];
    var good = result.level.n === 1;
    var shown = result.challenges.filter(function (c) { return good || c.key.indexOf("p_") !== 0; });
    if (!shown.length) shown = result.challenges;
    var phrases = shown.slice(0, 2).map(function (c) { return TAGS[c.key].phrase; });
    return {
      theme: theme,
      level: result.level.n,
      topic: g.topic,
      heroKicker: g.heroKicker,
      headline: good ? "You're already doing a lot right. Here's how to go further." : g.headline,
      lead: good
        ? "Your answers suggest your habits are in good shape, with a little room to improve: " + joinList(phrases) + "."
        : "Your answers suggest that " + joinList(phrases) + " may be making it harder than it needs to be.",
      body: (good ? "You already have solid habits in place, so for you this book is about polishing them. " : "") + g.body,
      solves: g.solves,
      cta: g.cta,
      target: g.target,
      targetName: g.targetName
    };
  }

  return {
    AREAS: AREAS, LEVELS: LEVELS, QUESTIONS: QUESTIONS, TAGS: TAGS, ACTIONS: ACTIONS,
    THEMES: THEMES, BOOK_ITEMS: BOOK_ITEMS,
    areaMaxima: areaMaxima, validateAnswers: validateAnswers, levelFor: levelFor,
    scoreAnswers: scoreAnswers, buildResult: buildResult, capitalise: capitalise,
    GATE: GATE, gateMessage: gateMessage
  };
});
